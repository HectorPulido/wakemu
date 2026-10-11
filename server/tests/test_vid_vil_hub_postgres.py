"""Isolated PostgreSQL lifecycle for Vid Vil's literal hub revisit."""
import hashlib
import json
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
REPORT = ROOT / "docs/reports/dungeons/VID-VIL-NATIVE-HUB-CANDIDATE-V11-20261010.json"
CONFIG = ROOT / ".runtime/local/vid-vil-native-hub-v11-20261010/native_dungeon_115.json"


class VidVilHubPostgresTests(PostgresCase):
    player = Fixture.player
    party = Fixture.party

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0

    @staticmethod
    def _edges(topology):
        return {
            (tuple(a), tuple(b)) for a, b in topology["exploration_geometry"]["edges"]
        }

    def walk_to(self, topology, start, targets, room_order, unlocked):
        edges = self._edges(topology)
        room_cells = {
            tuple(cell): room["order"]
            for room in topology["rooms"]
            for cell in room["cells"]
        }
        targets = set(map(tuple, targets))
        queue = [tuple(start)]
        previous = {tuple(start): None}
        found = None
        for cell in queue:
            if cell in targets:
                found = cell
                break
            for source, destination in edges:
                if (
                    source == cell
                    and destination not in previous
                    and room_cells.get(destination) == room_order
                    and room_cells.get(destination) <= unlocked
                ):
                    previous[destination] = cell
                    queue.append(destination)
        if found is None:
            raise AssertionError(
                f"No literal same-room walk from {start} to {targets} in room {room_order}"
            )
        path = []
        cell = found
        while cell is not None:
            path.append(cell)
            cell = previous[cell]
        path.reverse()
        return {
            "start_position": dict(zip(("x", "y", "z"), path[0])),
            "end_position": dict(zip(("x", "y", "z"), path[-1])),
            "steps": [
                dict(dx=b[0] - a[0], dy=b[1] - a[1], dz=b[2] - a[2])
                for a, b in zip(path, path[1:])
            ],
        }

    def test_four_room_hub_gate_receipts_return_party_outbox_and_exit(self):
        report_bytes = REPORT.read_bytes()
        report = json.loads(report_bytes)
        self.assertEqual(len(report["records"]), 1)
        candidate = report["records"][0]
        config_bytes = CONFIG.read_bytes()
        candidate_config = json.loads(config_bytes)
        self.assertEqual(
            dungeon_runtime_config.canonical_hash(candidate_config),
            candidate["configuration_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(config_bytes).hexdigest(),
            "6d082d4cc46ff43b2f959c9e1f242d02bb6b847dfca112a29d325ed744db5ac3",
        )
        config = candidate_config
        topology, route = config["topology"], config["route"]
        self.assertEqual([room["order"] for room in topology["rooms"]], [1, 2, 3, 4])
        self.assertEqual(topology["policy"], dungeon_native_flow.MIXED_POLICY)
        bindings = {binding["source_id"]: binding for binding in topology["doors"]}
        self.assertEqual(bindings[26747]["progression_gate_room"], 3)
        self.assertEqual(bindings[26748]["progression_gate_room"], 3)
        self.assertEqual(
            dungeon_native_flow.validate_transport_binding(topology, bindings[26747]), 3
        )
        self.assertEqual(
            dungeon_native_flow.validate_transport_binding(topology, bindings[26748]), 3
        )

        originals = dungeon_instances._ROUTES
        self.addCleanup(setattr, dungeon_instances, "_ROUTES", originals)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s::jsonb) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (json.dumps({"schema_version": 1, "routes": [route]}),),
            )
            dungeon_runtime_config.install_configuration(db, config)
        dungeon_instances.load_runtime_routes(self.store)

        groups = combat_group_store.PersistentGroups(self.store)
        geometry = map_geometry(route["start_map_id"])
        members, party_id = self.party(6)
        for member in members:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0 WHERE id=%s",
                    (route["entry_map_id"], member["character"]["id"]),
                )
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

        def frontier():
            with self.store.connection() as db:
                return db.execute(
                    "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["current_room"]

        def place_all(point):
            with self.store.connection() as db:
                for member in members:
                    db.execute(
                        "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                        (
                            route["start_map_id"],
                            instance,
                            *point,
                            member["character"]["id"],
                        ),
                    )

        def source_position(source_id):
            source = generic_transports.source(route["start_map_id"], source_id)
            self.assertIsNotNone(source, f"Native transport {source_id} is absent")
            return source

        def travel(source_id, *, expected_gate):
            binding = bindings[source_id]
            self.assertEqual(
                dungeon_native_flow.validate_transport_binding(topology, binding),
                expected_gate,
            )
            source = source_position(source_id)
            with self.store.connection() as db:
                actor = db.execute(
                    "SELECT x,y,z FROM characters WHERE id=%s",
                    (members[0]["character"]["id"],),
                ).fetchone()
            request = self.walk_to(
                topology,
                tuple(actor[key] for key in ("x", "y", "z")),
                binding["native_approach_cells"],
                binding["source_room"],
                frontier(),
            )
            dungeon_native_flow.validate_movement(
                topology, request, unlocked_room=frontier()
            )
            place_all(tuple(request["end_position"][key] for key in ("x", "y", "z")))
            response = dungeon_doors.advance(
                self.store,
                members[0]["account"],
                members[0]["generation"],
                members[0]["character"]["id"],
                struct.pack(">qiBi", source_id, binding["destination_id"], 0, 2),
                source_allowed=lambda actor, row: (
                    row["id"] == source_id
                    and [actor[k] for k in ("x", "y", "z")]
                    in binding["native_approach_cells"]
                ),
                room_for_position=lambda map_id, x, y, z: next(
                    room["order"]
                    for room in topology["rooms"]
                    if [x, y, z] in room["cells"]
                ),
                in_fight=lambda _: False,
                topology=topology,
            )
            self.assertEqual(len(response["members"]), 6)
            self.assertEqual(
                set(response["members"]), {m["character"]["id"] for m in members}
            )
            for member in members:
                actor = self.store.character(
                    member["account"], member["character"]["id"]
                )
                self.assertEqual(
                    (
                        actor["map_id"],
                        actor["instance_id"],
                        actor["x"],
                        actor["y"],
                        actor["z"],
                    ),
                    (route["start_map_id"], instance, *binding["destination_position"]),
                )
            with self.store.connection() as db:
                pending = db.execute(
                    "SELECT transition_revision,character_id,destination_x,destination_y,destination_z "
                    "FROM dungeon_transition_outbox WHERE instance_id=%s AND status='pending'",
                    (instance,),
                ).fetchall()
                self.assertEqual(len(pending), 6)
                self.assertEqual(
                    len({row["transition_revision"] for row in pending}), 1
                )
                self.assertEqual(
                    {row["character_id"] for row in pending},
                    {m["character"]["id"] for m in members},
                )
                self.assertEqual(
                    {
                        (
                            row["destination_x"],
                            row["destination_y"],
                            row["destination_z"],
                        )
                        for row in pending
                    },
                    {tuple(binding["destination_position"])},
                )
            # A retried packet after the atomic party move no longer originates
            # at the literal native approach cell and cannot create another
            # transition revision or a second batch of pending rows.
            with self.assertRaisesRegex(ValueError, "not authorized"):
                dungeon_doors.advance(
                    self.store,
                    members[0]["account"],
                    members[0]["generation"],
                    members[0]["character"]["id"],
                    struct.pack(">qiBi", source_id, binding["destination_id"], 0, 2),
                    source_allowed=lambda actor, row: (
                        row["id"] == source_id
                        and [actor[k] for k in ("x", "y", "z")]
                        in binding["native_approach_cells"]
                    ),
                    room_for_position=lambda map_id, x, y, z: next(
                        room["order"]
                        for room in topology["rooms"]
                        if [x, y, z] in room["cells"]
                    ),
                    in_fight=lambda _: False,
                    topology=topology,
                )
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(DISTINCT transition_revision) AS n "
                        "FROM dungeon_transition_outbox WHERE instance_id=%s AND status='pending'",
                        (instance,),
                    ).fetchone()["n"],
                    1,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM dungeon_transition_outbox "
                        "WHERE instance_id=%s AND status='pending'",
                        (instance,),
                    ).fetchone()["n"],
                    6,
                )
            return response

        def win(order):
            with self.store.connection() as db:
                spawned = dungeon_runtime.ensure_current_room(
                    db, groups, instance, geometry
                )
                self.assertIsNotNone(spawned)
                self.assertEqual(spawned["room_order"], order)
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
                for member in members:
                    db.execute(
                        "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                        "VALUES(%s,%s,%s,0)",
                        (fight_id, member["character"]["id"], member["account"]),
                    )
                dungeon_progression.bind_encounter(
                    db,
                    instance,
                    party_id,
                    members[0]["character"]["id"],
                    fight_id,
                    player_team=0,
                )
                db.execute(
                    "UPDATE combat_fights SET status='finished' WHERE id=%s",
                    (fight_id,),
                )
                fight = SimpleNamespace(id=fight_id, phase="finished", winner=0)
                result = dungeon_progression.settle_encounter(db, fight)
                self.assertTrue(result["victory"])
                replay = dungeon_progression.settle_encounter(db, fight)
                self.assertTrue(replay["replay"])
                return result

        def assert_gate_packet(source_id, unlocked, should_be_open):
            packets = dungeon_native_flow.packets(
                topology,
                map_id=route["start_map_id"],
                instance_id=instance,
                unlocked_room=unlocked,
            )
            matches = [
                body
                for _, body in packets
                if struct.unpack_from(">q", body)[0] == source_id
            ]
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0][20], int(should_be_open))

        # Encounter 1 authorizes the first native arrival at the hub.
        win(1)
        travel(26745, expected_gate=1)
        self.assertEqual(frontier(), 2)

        # A room-2 victory advances the frontier to 3 but cannot authorize the
        # shortcut to room 4: that transport is explicitly gated by room 3.
        win(2)
        self.assertEqual(frontier(), 3)
        assert_gate_packet(26747, frontier(), False)
        early = bindings[26747]
        source_position(26747)
        with self.store.connection() as db:
            actor = db.execute(
                "SELECT x,y,z FROM characters WHERE id=%s",
                (members[0]["character"]["id"],),
            ).fetchone()
        approach = self.walk_to(
            topology,
            tuple(actor[k] for k in ("x", "y", "z")),
            early["native_approach_cells"],
            2,
            frontier(),
        )
        dungeon_native_flow.validate_movement(
            topology, approach, unlocked_room=frontier()
        )
        place_all(tuple(approach["end_position"][k] for k in ("x", "y", "z")))
        with self.assertRaisesRegex(ValueError, "committed victory"):
            dungeon_doors.advance(
                self.store,
                members[0]["account"],
                members[0]["generation"],
                members[0]["character"]["id"],
                struct.pack(">qiBi", 26747, early["destination_id"], 0, 2),
                source_allowed=lambda actor, row: row["id"] == 26747
                and [actor[k] for k in ("x", "y", "z")]
                in early["native_approach_cells"],
                room_for_position=lambda map_id, x, y, z: 2 if x == 93 else 4,
                in_fight=lambda _: False,
                topology=topology,
            )
        self.assertEqual(frontier(), 3)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox "
                    "WHERE instance_id=%s AND status='pending'",
                    (instance,),
                ).fetchone()["n"],
                6,
            )

        # Traverse the mandatory third room, then return 3→2 without changing
        # the durable frontier. Only its receipt unlocks the 2→4 hub port.
        travel(26751, expected_gate=2)
        win(3)
        self.assertEqual(frontier(), 4)
        travel(26750, expected_gate=2)
        self.assertEqual(frontier(), 4)
        assert_gate_packet(26747, frontier(), True)

        # The frontier alone and the earlier room-2 receipt are insufficient:
        # hide only the room-3 victory row and prove the hub shortcut stays
        # denied without changing party/outbox state.
        hub = bindings[26747]
        with self.store.connection() as db:
            actor = db.execute(
                "SELECT x,y,z FROM characters WHERE id=%s",
                (members[0]["character"]["id"],),
            ).fetchone()
        attempt = self.walk_to(
            topology,
            tuple(actor[key] for key in ("x", "y", "z")),
            hub["native_approach_cells"],
            2,
            frontier(),
        )
        dungeon_native_flow.validate_movement(
            topology, attempt, unlocked_room=frontier()
        )
        place_all(tuple(attempt["end_position"][key] for key in ("x", "y", "z")))
        with self.store.connection() as db:
            room3_fight = db.execute(
                "SELECT fight_id FROM dungeon_room_encounters "
                "WHERE instance_id=%s AND room_order=3 AND status='victory' "
                "ORDER BY result_revision DESC LIMIT 1",
                (instance,),
            ).fetchone()["fight_id"]
            room2_receipt = db.execute(
                "SELECT count(*) AS n FROM dungeon_room_encounters "
                "WHERE instance_id=%s AND room_order=2 AND status='victory'",
                (instance,),
            ).fetchone()["n"]
            self.assertEqual(room2_receipt, 1)
            db.execute(
                "UPDATE dungeon_room_encounters SET status='defeat' WHERE fight_id=%s",
                (room3_fight,),
            )
        try:
            with self.assertRaisesRegex(ValueError, "committed victory"):
                dungeon_doors.advance(
                    self.store,
                    members[0]["account"],
                    members[0]["generation"],
                    members[0]["character"]["id"],
                    struct.pack(">qiBi", 26747, hub["destination_id"], 0, 2),
                    source_allowed=lambda actor, source: source["id"] == 26747
                    and [actor[k] for k in ("x", "y", "z")]
                    in hub["native_approach_cells"],
                    room_for_position=lambda map_id, x, y, z: 2 if x == 93 else 4,
                    in_fight=lambda _: False,
                    topology=topology,
                )
        finally:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE dungeon_room_encounters SET status='victory' WHERE fight_id=%s",
                    (room3_fight,),
                )
        self.assertEqual(frontier(), 4)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox "
                    "WHERE instance_id=%s AND status='pending'",
                    (instance,),
                ).fetchone()["n"],
                6,
            )
        travel(26747, expected_gate=3)
        self.assertEqual(frontier(), 4)
        final_result = win(4)
        self.assertTrue(final_result["victory"])

        # The reviewed 4→2 return is available once its explicit room-3 gate
        # has been reached. It preserves the completed frontier; the same
        # room-3 receipt permits the native 2→4 return trip.
        travel(26748, expected_gate=3)
        self.assertEqual(frontier(), 4)
        travel(26747, expected_gate=3)
        self.assertEqual(frontier(), 4)

        exit_binding = next(
            item
            for item in topology["physical_exit_objects"]
            if item["source_id"] == 26749
        )
        packets = dungeon_native_flow.packets(
            topology,
            map_id=route["start_map_id"],
            instance_id=instance,
            unlocked_room=4,
            completed=True,
        )
        exit_body = next(
            body for _, body in packets if struct.unpack_from(">q", body)[0] == 26749
        )
        self.assertEqual(exit_body[19:21], bytes((1, 1)))
        place_all(exit_binding["native_approach_cells"][0])
        for member in members:
            dungeon_exit.leave(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
                struct.pack(">qiBi", 26749, exit_binding["destination_id"], 0, 2),
                source_allowed=lambda actor, source: source["id"] == 26749
                and [actor[k] for k in ("x", "y", "z")]
                in exit_binding["native_approach_cells"],
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
                dict(
                    db.execute(
                        "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
                        (instance,),
                    ).fetchone()
                ),
                {"current_room": 4, "status": "completed"},
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
                    "SELECT count(*) AS n FROM dungeon_room_encounters "
                    "WHERE instance_id=%s AND status='victory'",
                    (instance,),
                ).fetchone()["n"],
                4,
            )
        self.assertEqual(
            hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
            "6d082d4cc46ff43b2f959c9e1f242d02bb6b847dfca112a29d325ed744db5ac3",
        )

        evidence_path = os.environ.get("WAKFU_DUNGEON_LIFECYCLE_AUDIT")
        if evidence_path:
            evidence = Path(evidence_path)
            evidence.parent.mkdir(parents=True, exist_ok=True)
            source_paths = (
                "server/tests/test_vid_vil_hub_postgres.py",
                "server/local_game_server.py",
                "server/wakfu_server/maps/dungeon_doors.py",
                "server/wakfu_server/maps/dungeon_branches.py",
                "server/wakfu_server/maps/dungeon_native_flow.py",
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
                path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                for path in source_paths
            }
            hashes[str(REPORT.relative_to(ROOT))] = hashlib.sha256(
                report_bytes
            ).hexdigest()
            hashes[str(CONFIG.relative_to(ROOT))] = hashlib.sha256(
                config_bytes
            ).hexdigest()
            evidence.write_text(
                json.dumps(
                    {
                        "scope": "Isolated PostgreSQL Vid Vil 4-room hub transport lifecycle; six-member party; explicit room-3 receipt gate on 2→4; backward 3→2; replay and atomic outbox; final native exit. Combat is settled with authoritative dungeon receipts; combat mechanics are not simulated.",
                        "runtime_activated": False,
                        "source_sha256": hashes,
                        "records": [
                            {
                                "route": route["key"],
                                "rooms": 4,
                                "players": 6,
                                "mandatory_room_receipts": 4,
                                "nonadjacent_gate_room": 3,
                                "early_2_to_4_after_room_2_victory": "rejected",
                                "2_to_4_after_room_3_victory": "accepted",
                                "backward_3_to_2": "accepted_without_progress_change",
                                "backward_4_to_2": "accepted_without_progress_change",
                                "forward_2_to_4_after_room_4_victory": "accepted",
                                "door_replay": "blocked_by_source_position_after_atomic_party_move",
                                "encounter_receipt_replay": "idempotent",
                                "final_native_exit": "accepted_and_run_closed",
                                "status": "isolated_postgres_hub_lifecycle_passed",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n"
            )


del Fixture
