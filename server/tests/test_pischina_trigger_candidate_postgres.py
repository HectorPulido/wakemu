"""Isolated PostgreSQL lifecycle for La Pischina's native trigger-cut arenas."""
import hashlib
import json
import os
import struct
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace

from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as Fixture
from wakfu_server import (
    combat_group_store,
    dungeon_exit,
    dungeon_instances,
    dungeon_native_flow,
    dungeon_progression,
    dungeon_runtime,
    dungeon_runtime_config,
    dungeon_transport,
    generic_transports,
)
from wakfu_server.combat_terrain import map_geometry

ROOT = Path(__file__).resolve().parents[2]
REPORT = (
    ROOT / "docs/reports/dungeons/PISCHINA-NATIVE-TRIGGER-CANDIDATE-V10-20261010.json"
)
CONFIG_PATH = (
    ROOT / ".runtime/local/pischina-native-trigger-v10-20261010/native_dungeon_143.json"
)
GEOMETRY_PATH = (
    ROOT / "docs/reports/dungeons/PISCHINA-NATIVE-ARENA-GEOMETRY-20261010.json"
)
NATIVE_EXPLORATION_PATH = (
    ROOT / ".runtime/local/all-native-dungeon-exploration/exploration-912.json"
)


class PischinaNativeTriggerPostgresTests(PostgresCase):
    player = Fixture.player
    party = Fixture.party

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0

    @staticmethod
    def path(topology, start, target, *, max_room):
        """Find an actual directed native walk path without adding graph edges."""
        owner = {
            tuple(cell): room["order"]
            for room in topology["rooms"]
            for cell in room["cells"]
        }
        edges = {
            (tuple(a), tuple(b)) for a, b in topology["exploration_geometry"]["edges"]
        }
        start, target = tuple(start), tuple(target)
        queue = deque([start])
        previous = {start: None}
        while queue:
            current = queue.popleft()
            if current == target:
                break
            for source, destination in edges:
                if (
                    source == current
                    and destination not in previous
                    and owner.get(destination, max_room + 1) <= max_room
                ):
                    previous[destination] = current
                    queue.append(destination)
        if target not in previous:
            raise AssertionError(f"No literal native path from {start} to {target}")
        cells = []
        current = target
        while current is not None:
            cells.append(current)
            current = previous[current]
        cells.reverse()
        return dict(
            start_position=dict(zip(("x", "y", "z"), cells[0])),
            end_position=dict(zip(("x", "y", "z"), cells[-1])),
            steps=[
                dict(dx=b[0] - a[0], dy=b[1] - a[1], dz=b[2] - a[2])
                for a, b in zip(cells, cells[1:])
            ],
        )

    @classmethod
    def trigger_path(cls, topology, start, gate):
        edges = {
            (tuple(a), tuple(b)) for a, b in topology["exploration_geometry"]["edges"]
        }
        owner = {
            tuple(cell): room["order"]
            for room in topology["rooms"]
            for cell in room["cells"]
        }
        trigger = tuple(gate["position"])
        source_neighbors = sorted(
            a for a, b in edges if b == trigger and owner.get(a) == gate["source_room"]
        )
        destination_neighbors = sorted(
            b
            for a, b in edges
            if a == trigger and owner.get(b) == gate["destination_room"]
        )
        if not source_neighbors or not destination_neighbors:
            raise AssertionError(f"Trigger {gate['source_id']} has no native cut edges")
        prefix = cls.path(
            topology, start, source_neighbors[0], max_room=gate["source_room"]
        )
        points = [tuple(prefix["start_position"][k] for k in ("x", "y", "z"))]
        current = points[0]
        for step in prefix["steps"]:
            current = tuple(
                current[i] + step["d" + axis] for i, axis in enumerate(("x", "y", "z"))
            )
            points.append(current)
        points.extend((trigger, destination_neighbors[0]))
        return dict(
            start_position=dict(zip(("x", "y", "z"), points[0])),
            end_position=dict(zip(("x", "y", "z"), points[-1])),
            steps=[
                dict(dx=b[0] - a[0], dy=b[1] - a[1], dz=b[2] - a[2])
                for a, b in zip(points, points[1:])
            ],
        )

    def test_four_native_trigger_frontiers_and_six_player_lifecycle(self):
        report_bytes = REPORT.read_bytes()
        report = json.loads(report_bytes)
        record = next(
            r for r in report["records"] if r["route"] == "native_dungeon_143"
        )
        self.assertEqual(record["status"], "offline_configuration_prepared")
        config_bytes = CONFIG_PATH.read_bytes()
        source_config = json.loads(config_bytes)
        route = source_config["route"]
        topology = source_config["topology"]
        self.assertEqual(route["key"], "native_dungeon_143")
        self.assertEqual(topology["policy"], dungeon_native_flow.MIXED_POLICY)
        self.assertEqual(len(topology["rooms"]), 4)
        native_exploration = json.loads(NATIVE_EXPLORATION_PATH.read_text())
        self.assertEqual(
            set(map(tuple, topology["exploration_geometry"]["cells"])),
            set(map(tuple, native_exploration["cells"])),
        )
        self.assertEqual(
            {
                (tuple(a), tuple(b))
                for a, b in topology["exploration_geometry"]["edges"]
            },
            {(tuple(a), tuple(b)) for a, b in native_exploration["edges"]},
            "candidate movement graph must equal the frozen native export",
        )
        self.assertEqual(
            [(r["order"], len(r["cells"])) for r in topology["rooms"]],
            [(1, 220), (2, 184), (3, 486), (4, 272)],
        )

        expected = {
            31447: ((24, 15, 1), 1, 2),
            31448: ((33, 6, 1), 2, 3),
            31449: ((52, -4, 1), 3, 4),
            31450: ((53, -4, 1), 3, 4),
        }
        gates = {gate["source_id"]: gate for gate in topology["position_trigger_gates"]}
        self.assertEqual(set(gates), set(expected))
        owner = {
            tuple(cell): room["order"]
            for room in topology["rooms"]
            for cell in room["cells"]
        }
        for source_id, (position, source_room, destination_room) in expected.items():
            gate = gates[source_id]
            self.assertEqual(tuple(gate["position"]), position)
            self.assertEqual(
                (gate["source_room"], gate["destination_room"]),
                (source_room, destination_room),
            )
            self.assertEqual(owner[position], destination_room)
            self.assertNotIn(
                source_id, {d["source_id"] for d in topology["physical_doors"]}
            )
        # Both parallel PositionTriggers are independent movement cut cells.
        self.assertEqual(
            [g["source_id"] for g in gates.values() if g["source_room"] == 3],
            [31449, 31450],
        )

        original_routes = dungeon_instances._ROUTES
        self.addCleanup(setattr, dungeon_instances, "_ROUTES", original_routes)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s::jsonb) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (json.dumps(dict(schema_version=1, routes=[route])),),
            )
        dungeon_instances.load_runtime_routes(self.store)
        config = dungeon_runtime_config.prepare_configuration(
            source_config["compiled_plan"],
            topology,
            route,
            version=10040,
            provenance=source_config["provenance"],
        )
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, config)

        members, party_id = self.party(6)
        for member in members:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0 WHERE id=%s",
                    (route["entry_map_id"], member["character"]["id"]),
                )
        groups = combat_group_store.PersistentGroups(self.store)
        geometry = map_geometry(route["start_map_id"])
        run = dungeon_transport.enter(
            self.store,
            members[0]["account"],
            members[0]["generation"],
            members[0]["character"]["id"],
            route["entry_map_id"],
            struct.pack(
                ">qiBi", route["entry_object_id"], route["destination_id"], 0, 2
            ),
            criterion_allowed=lambda actor, criterion: True,
            source_allowed=lambda actor, source: True,
            resolve_destination=dungeon_runtime.entry_destination,
            initialize_instance=lambda db, session: dungeon_runtime.initialize_instance(
                db,
                session,
                groups=groups,
                geometry=geometry,
            ),
        )
        instance = run["instance_id"]
        self.assertEqual(len(run["transition"]["members"]), 6)
        self.assertEqual(
            len(
                dungeon_instances.pending_transitions(
                    self.store,
                    members[0]["account"],
                    members[0]["generation"],
                    members[0]["character"]["id"],
                )
            ),
            1,
        )
        arrivals = [
            self.store.character(m["account"], m["character"]["id"]) for m in members
        ]
        self.assertEqual({a["map_id"] for a in arrivals}, {route["start_map_id"]})
        self.assertEqual({a["instance_id"] for a in arrivals}, {instance})
        self.assertEqual(
            {(a["x"], a["y"], a["z"]) for a in arrivals},
            {(arrivals[0]["x"], arrivals[0]["y"], arrivals[0]["z"])},
        )
        start = tuple(arrivals[0][k] for k in ("x", "y", "z"))
        self.assertEqual(
            owner.get(start), 1, f"native entry arrived outside room one: {start}"
        )

        def frontier():
            with self.store.connection() as db:
                return db.execute(
                    "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["current_room"]

        def move_party(request, expected_frontier):
            endpoint = dungeon_native_flow.validate_movement(
                topology, request, unlocked_room=expected_frontier
            )
            for member in members:
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s AND instance_id=%s",
                        (*endpoint, member["character"]["id"], instance),
                    )
            for member in members:
                actor = self.store.character(
                    member["account"], member["character"]["id"]
                )
                self.assertEqual((actor["x"], actor["y"], actor["z"]), endpoint)

        def finish_room(order):
            with self.store.connection() as db:
                spawned = dungeon_runtime.ensure_current_room(
                    db, groups, instance, geometry
                )
                self.assertIsNotNone(spawned)
                self.assertEqual(spawned["room_order"], order)
                fight = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
                for member in members:
                    db.execute(
                        "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                        "VALUES(%s,%s,%s,0)",
                        (fight, member["character"]["id"], member["account"]),
                    )
                dungeon_progression.bind_encounter(
                    db,
                    instance,
                    party_id,
                    members[0]["character"]["id"],
                    fight,
                    player_team=0,
                )
                db.execute(
                    "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight,)
                )
                result = dungeon_progression.settle_encounter(
                    db, SimpleNamespace(id=fight, phase="finished", winner=0)
                )
                self.assertTrue(result["victory"])
                self.assertTrue(
                    dungeon_progression.settle_encounter(
                        db, SimpleNamespace(id=fight, phase="finished", winner=0)
                    )["replay"]
                )
                return result

        selected_transitions = []
        for order in range(1, 4):
            current = self.store.character(
                members[0]["account"], members[0]["character"]["id"]
            )
            position = tuple(current[k] for k in ("x", "y", "z"))
            frontier_gates = [
                g
                for g in topology["position_trigger_gates"]
                if g["source_room"] == order
            ]
            self.assertTrue(frontier_gates, f"missing trigger frontier {order}")
            requests = {
                g["source_id"]: self.trigger_path(topology, position, g)
                for g in frontier_gates
            }
            next_anchor = tuple(
                record["placement_validation"]["rooms"][order]["anchor"]
            )
            bypass_probe = self.path(
                topology, position, next_anchor, max_room=order + 1
            )
            # Try the shortest real-edge route directly to the next arena as a
            # bypass probe. Even if it avoids a chosen source ID, the locked
            # future-stage cell must keep the route unavailable before victory.
            with self.assertRaises(ValueError):
                dungeon_native_flow.validate_movement(
                    topology, bypass_probe, unlocked_room=order
                )
            # Every exact trigger crossing is rejected until that room has a
            # durable victory receipt. This includes both parallel stage-3 gates.
            for source_id, request in requests.items():
                with self.assertRaises(ValueError):
                    dungeon_native_flow.validate_movement(
                        topology, request, unlocked_room=order
                    )
            finish_room(order)
            self.assertEqual(frontier(), order + 1)
            dungeon_native_flow.validate_movement(
                topology, bypass_probe, unlocked_room=order + 1
            )
            for source_id, request in requests.items():
                endpoint = dungeon_native_flow.validate_movement(
                    topology, request, unlocked_room=order + 1
                )
                self.assertEqual(owner[endpoint], order + 1)
            primary = frontier_gates[0]
            move_party(requests[primary["source_id"]], order + 1)
            selected_transitions.append(primary["source_id"])

        self.assertEqual(selected_transitions, [31447, 31448, 31449])
        self.assertEqual(frontier(), 4)
        finish_room(4)
        exits = {e["source_id"]: e for e in topology["physical_exit_objects"]}
        exit_binding = exits[24197]
        native_exit = generic_transports.source(
            route["start_map_id"], exit_binding["source_id"]
        )
        self.assertIsNotNone(native_exit)
        for member in members:
            current = self.store.character(member["account"], member["character"]["id"])
            position = tuple(current[k] for k in ("x", "y", "z"))
            walk = self.path(
                topology, position, exit_binding["native_approach_cells"][0], max_room=4
            )
            move_party(walk, 4)
        packets_before = dungeon_native_flow.packets(
            topology,
            map_id=route["start_map_id"],
            instance_id=instance,
            unlocked_room=4,
            completed=False,
        )
        body_before = next(
            body
            for _, body in packets_before
            if struct.unpack_from(">q", body)[0] == exit_binding["source_id"]
        )
        self.assertEqual(body_before[19:21], bytes((0, 0)))
        packets_after = dungeon_native_flow.packets(
            topology,
            map_id=route["start_map_id"],
            instance_id=instance,
            unlocked_room=4,
            completed=True,
        )
        body_after = next(
            body
            for _, body in packets_after
            if struct.unpack_from(">q", body)[0] == exit_binding["source_id"]
        )
        self.assertEqual(body_after[19:21], bytes((1, 1)))
        for member in members:
            dungeon_exit.leave(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
                struct.pack(
                    ">qiBi",
                    exit_binding["source_id"],
                    exit_binding["destination_id"],
                    0,
                    2,
                ),
                source_allowed=lambda actor, source: (
                    source["id"] == exit_binding["source_id"]
                    and [actor[k] for k in ("x", "y", "z")]
                    in exit_binding["native_approach_cells"]
                ),
                in_fight=lambda _: False,
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_instances WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["status"],
                "closed",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["n"],
                4,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_room_encounters WHERE instance_id=%s AND status='victory'",
                    (instance,),
                ).fetchone()["n"],
                4,
            )

        self.assertEqual(
            hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
            hashlib.sha256(config_bytes).hexdigest(),
        )
        audit_path = os.environ.get("WAKFU_DUNGEON_LIFECYCLE_AUDIT")
        if audit_path:
            sources = (
                "server/tests/test_pischina_trigger_candidate_postgres.py",
                "server/local_game_server.py",
                "server/wakfu_server/maps/dungeon_branches.py",
                "server/wakfu_server/maps/dungeon_doors.py",
                "server/wakfu_server/maps/dungeon_native_flow.py",
                "server/wakfu_server/maps/dungeon_physical_doors.py",
                "server/wakfu_server/maps/dungeon_object_states.py",
                "server/wakfu_server/maps/dungeon_progression.py",
                "server/wakfu_server/maps/dungeon_runtime.py",
                "server/wakfu_server/maps/dungeon_runtime_config.py",
                "server/wakfu_server/maps/dungeon_instances.py",
                "server/wakfu_server/maps/dungeon_transport.py",
                "server/wakfu_server/maps/dungeon_room_spawns.py",
                "server/wakfu_server/maps/dungeon_exit.py",
                "server/migrations/112_dungeon_branch_selection.sql",
            )
            hashes = {
                p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources
            }
            hashes[record["path"]] = hashlib.sha256(config_bytes).hexdigest()
            hashes[
                "candidate_report:docs/reports/dungeons/PISCHINA-NATIVE-TRIGGER-CANDIDATE-V10-20261010.json"
            ] = hashlib.sha256(report_bytes).hexdigest()
            hashes[
                "geometry_evidence:docs/reports/dungeons/PISCHINA-NATIVE-ARENA-GEOMETRY-20261010.json"
            ] = hashlib.sha256(GEOMETRY_PATH.read_bytes()).hexdigest()
            hashes[
                "native_exploration:.runtime/local/all-native-dungeon-exploration/exploration-912.json"
            ] = hashlib.sha256(NATIVE_EXPLORATION_PATH.read_bytes()).hexdigest()
            output = Path(audit_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(
                    {
                        "scope": "Isolated PostgreSQL lifecycle for four native La Pischina trigger-cut arenas; exact PositionTrigger movement frontiers, six player arrivals and native final exit; no runtime activation or combat/spell behavior simulation",
                        "runtime_activated": False,
                        "source_sha256": hashes,
                        "records": [
                            {
                                "route": route["key"],
                                "status": "isolated_postgres_trigger_lifecycle_passed",
                                "rooms": 4,
                                "players": 6,
                                "victory_receipts": 4,
                                "room_spawn_receipts": 4,
                                "position_trigger_gates": [31447, 31448, 31449, 31450],
                                "trigger_frontier_progression": selected_transitions,
                                "parallel_stage3_gates_closed_until_receipt": [
                                    31449,
                                    31450,
                                ],
                                "native_exit_after_final_victory": exit_binding[
                                    "source_id"
                                ],
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n"
            )


del Fixture
