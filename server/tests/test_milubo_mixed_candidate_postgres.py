"""PostgreSQL gate for the prepared four-stage native mixed Milubo route."""
import json
import hashlib
import os
import struct
import unittest
from pathlib import Path
from types import SimpleNamespace

from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as Fixture
from wakfu_server import (
    combat_group_store,
    dungeon_doors,
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
REPORT = ROOT / "docs/reports/dungeons/MILUBO-FOUR-ROOM-MIXED-CANDIDATE-20261010.json"


class MiluboMixedCandidatePostgresTests(PostgresCase):
    player = Fixture.player
    party = Fixture.party

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0

    @staticmethod
    def walk_request(topology, start, end):
        edges = {
            (tuple(a), tuple(b)) for a, b in topology["exploration_geometry"]["edges"]
        }
        queue = [tuple(start)]
        previous = {tuple(start): None}
        for cell in queue:
            if cell == tuple(end):
                break
            for a, b in edges:
                if a == cell and b not in previous:
                    previous[b] = cell
                    queue.append(b)
        if tuple(end) not in previous:
            raise AssertionError(f"No native walk path from {start} to {end}")
        path = []
        cell = tuple(end)
        while cell is not None:
            path.append(cell)
            cell = previous[cell]
        path.reverse()
        return dict(
            start_position=dict(zip(("x", "y", "z"), path[0])),
            end_position=dict(zip(("x", "y", "z"), path[-1])),
            steps=[
                dict(dx=b[0] - a[0], dy=b[1] - a[1], dz=b[2] - a[2])
                for a, b in zip(path, path[1:])
            ],
        )

    @staticmethod
    def gate_walk(topology, gate):
        edges = {
            (tuple(a), tuple(b)) for a, b in topology["exploration_geometry"]["edges"]
        }
        sources = {
            tuple(c) for c in topology["rooms"][gate["source_room"] - 1]["cells"]
        }
        targets = {
            tuple(c) for c in topology["rooms"][gate["destination_room"] - 1]["cells"]
        }
        point = tuple(gate["position"])
        starts = sorted(a for a, b in edges if b == point and a in sources)
        ends = sorted(b for a, b in edges if a == point and b in targets)
        if not starts or not ends:
            raise AssertionError(f"Gate {gate['source_id']} has no literal walk edge")
        path = (starts[0], point, ends[0])
        return dict(
            start_position=dict(zip(("x", "y", "z"), path[0])),
            end_position=dict(zip(("x", "y", "z"), path[-1])),
            steps=[
                dict(dx=b[0] - a[0], dy=b[1] - a[1], dz=b[2] - a[2])
                for a, b in zip(path, path[1:])
            ],
        )

    def test_four_room_mixed_native_lifecycle_with_six_players(self):
        record = json.loads(REPORT.read_text())["records"][0]
        config_path = ROOT / record["path"]
        config_bytes = config_path.read_bytes()
        source_config = json.loads(config_bytes)
        route = source_config["route"]
        topology = source_config["topology"]
        self.assertEqual(topology["policy"], dungeon_native_flow.MIXED_POLICY)
        self.assertEqual(len(topology["rooms"]), 4)

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
            version=10001,
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

        def enter():
            return dungeon_transport.enter(
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
                    db, session, groups=groups, geometry=geometry
                ),
            )

        run = enter()
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

        def room_for_position(map_id, x, y, z):
            point = (x, y, z)
            for room in topology["rooms"]:
                if point in {tuple(cell) for cell in room["cells"]}:
                    return room["order"]
            for binding in topology["doors"]:
                if point == tuple(binding["destination_position"]):
                    return binding["destination_room"]
            return None

        def place_party(point):
            for member in members:
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                        (
                            route["start_map_id"],
                            instance,
                            *point,
                            member["character"]["id"],
                        ),
                    )

        def native_door(source_id):
            binding = next(d for d in topology["doors"] if d["source_id"] == source_id)
            place_party(binding["source_position"])
            source = generic_transports.source(route["start_map_id"], source_id)
            self.assertIsNotNone(
                source, f"native transport {source_id} missing from catalog"
            )
            destination_id = binding["destination_id"]
            result = dungeon_doors.advance(
                self.store,
                members[0]["account"],
                members[0]["generation"],
                members[0]["character"]["id"],
                struct.pack(">qiBi", source_id, destination_id, 0, 2),
                source_allowed=lambda actor, candidate: (
                    candidate["id"] == source_id
                    and [actor[k] for k in ("x", "y", "z")]
                    in binding["native_approach_cells"]
                ),
                room_for_position=room_for_position,
                in_fight=lambda _: False,
                topology=topology,
            )
            self.assertEqual(len(result["members"]), 6)
            for member in members:
                actor = self.store.character(
                    member["account"], member["character"]["id"]
                )
                self.assertEqual(
                    tuple(actor[k] for k in ("x", "y", "z")),
                    tuple(binding["destination_position"]),
                )
            return result

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
                replay = dungeon_progression.settle_encounter(
                    db, SimpleNamespace(id=fight, phase="finished", winner=0)
                )
                self.assertTrue(replay["replay"])
                return result

        # The physical 1→2 gate is closed before its receipt and walkable after.
        first_gate = next(
            g for g in topology["physical_doors"] if g["source_room"] == 1
        )
        gate_request = self.gate_walk(topology, first_gate)
        with self.assertRaisesRegex(ValueError, "locked room"):
            dungeon_native_flow.validate_movement(
                topology, gate_request, unlocked_room=1
            )
        result = finish_room(1)
        self.assertEqual(result["current_room"], 2)
        dungeon_native_flow.validate_movement(topology, gate_request, unlocked_room=2)

        # Both native directions are actual catalogued party transports and do not
        # increment the durable encounter frontier.
        same_stage = [
            d
            for d in topology["doors"]
            if d["source_room"] == d["destination_room"] == 2
        ]
        for binding in same_stage:
            native_door(binding["source_id"])
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                        (instance,),
                    ).fetchone()["current_room"],
                    2,
                )

        forward = next(
            d
            for d in topology["doors"]
            if d["source_room"] == 2 and d["destination_room"] == 3
        )
        place_party(forward["source_position"])
        with self.assertRaisesRegex(ValueError, "committed victory"):
            native_door(forward["source_id"])
        finish_room(2)
        moved = native_door(forward["source_id"])
        self.assertEqual(
            tuple(moved[k] for k in ("x", "y", "z")),
            tuple(forward["destination_position"]),
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["current_room"],
                3,
            )
        final_gate = next(
            g for g in topology["physical_doors"] if g["source_room"] == 3
        )
        final_walk = self.gate_walk(topology, final_gate)
        with self.assertRaisesRegex(ValueError, "locked room"):
            dungeon_native_flow.validate_movement(topology, final_walk, unlocked_room=3)
        finish_room(3)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["current_room"],
                4,
            )
        self.assertEqual(
            dungeon_native_flow.validate_movement(
                topology, final_walk, unlocked_room=4
            ),
            tuple(final_walk["end_position"][k] for k in ("x", "y", "z")),
        )
        # The room-four exterior is an actual native exit packet/request; it is
        # used only after the final receipt and closes the run after the party leaves.
        exit_binding = next(
            e for e in topology["physical_exit_objects"] if e["room_order"] == 4
        )
        source = generic_transports.source(
            route["start_map_id"], exit_binding["source_id"]
        )
        self.assertIsNotNone(source)
        before_packets = dungeon_native_flow.packets(
            topology,
            map_id=route["start_map_id"],
            instance_id=instance,
            unlocked_room=4,
            completed=False,
        )
        before_exit = next(
            body
            for opcode, body in before_packets
            if struct.unpack_from(">q", body)[0] == exit_binding["source_id"]
        )
        self.assertEqual(before_exit[19:21], bytes((0, 0)))
        finish_room(4)
        after_packets = dungeon_native_flow.packets(
            topology,
            map_id=route["start_map_id"],
            instance_id=instance,
            unlocked_room=4,
            completed=True,
        )
        after_exit = next(
            body
            for opcode, body in after_packets
            if struct.unpack_from(">q", body)[0] == exit_binding["source_id"]
        )
        self.assertEqual(after_exit[19:21], bytes((1, 1)))
        destination_id = exit_binding["destination_id"]
        place_party(exit_binding["native_approach_cells"][0])
        for member in members:
            dungeon_exit.leave(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
                struct.pack(">qiBi", exit_binding["source_id"], destination_id, 0, 2),
                source_allowed=lambda actor, candidate: (
                    candidate["id"] == exit_binding["source_id"]
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
        if os.environ.get("WAKFU_DUNGEON_LIFECYCLE_AUDIT"):
            evidence_path = Path(os.environ["WAKFU_DUNGEON_LIFECYCLE_AUDIT"])
            sources = (
                "server/tests/test_milubo_mixed_candidate_postgres.py",
                "server/local_game_server.py",
                "server/wakfu_server/maps/dungeon_doors.py",
                "server/wakfu_server/maps/dungeon_branches.py",
                "server/wakfu_server/maps/dungeon_native_flow.py",
                "server/wakfu_server/maps/dungeon_progression.py",
                "server/wakfu_server/maps/dungeon_physical_doors.py",
                "server/wakfu_server/maps/dungeon_runtime.py",
                "server/wakfu_server/maps/dungeon_runtime_config.py",
                "server/wakfu_server/maps/dungeon_object_states.py",
                "server/wakfu_server/maps/dungeon_instances.py",
                "server/wakfu_server/maps/dungeon_transport.py",
                "server/wakfu_server/maps/dungeon_room_spawns.py",
                "server/wakfu_server/maps/dungeon_exit.py",
                "server/migrations/112_dungeon_branch_selection.sql",
            )
            hashes = {
                source: hashlib.sha256((ROOT / source).read_bytes()).hexdigest()
                for source in sources
            }
            hashes[record["path"]] = hashlib.sha256(config_bytes).hexdigest()
            hashes[
                "candidate_report:docs/reports/dungeons/MILUBO-FOUR-ROOM-MIXED-CANDIDATE-20261010.json"
            ] = hashlib.sha256(REPORT.read_bytes()).hexdigest()
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text(
                json.dumps(
                    {
                        "scope": "Isolated PostgreSQL lifecycle for source-only four-room Milubo mixed traversal; authoritative victory receipts and native object requests, without boss AI or spell simulation",
                        "runtime_activated": False,
                        "source_sha256": hashes,
                        "records": [
                            {
                                "route": route["key"],
                                "status": "isolated_postgres_mixed_lifecycle_passed",
                                "players": 6,
                                "rooms": 4,
                                "victory_receipts": 4,
                                "room_spawn_receipts": 4,
                                "room2_same_stage_native_transports": [
                                    d["source_id"] for d in same_stage
                                ],
                                "pre_victory_room3_transport_blocked": forward[
                                    "source_id"
                                ],
                                "room3_forward_native_transport": forward["source_id"],
                                "physical_gates_locked_until_receipt": [
                                    first_gate["source_id"],
                                    final_gate["source_id"],
                                ],
                                "room4_native_exit_after_victory": exit_binding[
                                    "source_id"
                                ],
                                "runtime_activation": False,
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n"
            )


# Prevent unittest discovery from treating the imported fixture class as a
# second suite; only this candidate-specific test should run from this module.
del Fixture
