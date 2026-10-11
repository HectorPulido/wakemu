"""PostgreSQL lifecycle gate for Palacio Zollo's two native branch routes."""
import hashlib
import json
import os
import struct
from pathlib import Path
from types import SimpleNamespace
import unittest

from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as Fixture
from wakfu_server import (
    combat_group_store,
    dungeon_branches,
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
from wakfu_server.maps import dungeon_physical_doors
from wakfu_server.combat_terrain import map_geometry

ROOT = Path(__file__).resolve().parents[2]
REPORT = (
    ROOT
    / "docs/reports/dungeons/PALACIO-ZOLLO-NATIVE-CYCLE-CANDIDATE-V14-20261010.json"
)


class PalacioZolloBranchPostgresTests(PostgresCase):
    player = Fixture.player
    party = Fixture.party

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.record = json.loads(REPORT.read_text())["records"][0]
        self.config_path = ROOT / self.record["path"]
        self.config_bytes = self.config_path.read_bytes()
        self.source_config = json.loads(self.config_bytes)
        self.route = self.source_config["route"]
        self.topology = self.source_config["topology"]
        self.assertEqual(
            dungeon_runtime_config.canonical_hash(self.source_config),
            self.record["configuration_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(self.config_bytes).hexdigest(),
            self.record["configuration_file_sha256"],
        )
        self.assertEqual(
            self.source_config["evidence_hashes"],
            {
                "plan": dungeon_runtime_config.canonical_hash(
                    self.source_config["compiled_plan"]
                ),
                "topology": dungeon_runtime_config.canonical_hash(
                    self.source_config["topology"]
                ),
                "route": dungeon_runtime_config.canonical_hash(self.route),
            },
        )
        original_routes = dungeon_instances._ROUTES
        self.addCleanup(setattr, dungeon_instances, "_ROUTES", original_routes)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s::jsonb) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (json.dumps(dict(schema_version=1, routes=[self.route])),),
            )
        dungeon_instances.load_runtime_routes(self.store)
        self.pinned = dungeon_runtime_config.prepare_configuration(
            self.source_config["compiled_plan"],
            self.topology,
            self.route,
            version=13073,
            provenance=self.source_config["provenance"],
        )
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, self.pinned)
        self.groups = combat_group_store.PersistentGroups(self.store)
        self.geometry = map_geometry(self.route["start_map_id"])

    def _enter(self):
        members, party_id = self.party(6)
        for member in members:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0 WHERE id=%s",
                    (self.route["entry_map_id"], member["character"]["id"]),
                )
        result = dungeon_transport.enter(
            self.store,
            members[0]["account"],
            members[0]["generation"],
            members[0]["character"]["id"],
            self.route["entry_map_id"],
            struct.pack(
                ">qiBi",
                self.route["entry_object_id"],
                self.route["destination_id"],
                0,
                2,
            ),
            criterion_allowed=lambda _actor, _criterion: True,
            source_allowed=lambda _actor, source: source["id"]
            == self.route["entry_object_id"],
            resolve_destination=dungeon_runtime.entry_destination,
            initialize_instance=lambda db, session: dungeon_runtime.initialize_instance(
                db,
                session,
                groups=self.groups,
                geometry=self.geometry,
            ),
        )
        return members, party_id, result["instance_id"]

    def _place_party(self, members, instance, point):
        for member in members:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (
                        self.route["start_map_id"],
                        instance,
                        *point,
                        member["character"]["id"],
                    ),
                )

    def _room_for_position(self, map_id, x, y, z):
        config = dict(self.pinned, topology=self.topology)
        return dungeon_runtime.room_for_position(config, map_id, x, y, z)

    def _door(self, members, instance, source_id, *, callback=None):
        binding = next(d for d in self.topology["doors"] if d["source_id"] == source_id)
        self._place_party(members, instance, binding["native_approach_cells"][0])
        result = dungeon_doors.advance(
            self.store,
            members[0]["account"],
            members[0]["generation"],
            members[0]["character"]["id"],
            struct.pack(">qiBi", source_id, binding["destination_id"], 0, 2),
            source_allowed=lambda actor, source: (
                source["id"] == source_id
                and [actor[k] for k in ("x", "y", "z")]
                in binding["native_approach_cells"]
            ),
            room_for_position=self._room_for_position,
            in_fight=lambda _character: False,
            topology=self.topology,
            on_arrival=callback
            or (
                lambda db, instance_id: dungeon_runtime.ensure_current_room(
                    db, self.groups, instance_id, self.geometry
                )
            ),
        )
        self.assertEqual(len(result["members"]), 6)
        self.assertEqual(
            tuple(result[k] for k in ("x", "y", "z")),
            tuple(binding["destination_position"]),
        )
        return result

    def _finish(self, members, party_id, instance, order):
        with self.store.connection() as db:
            spawned = dungeon_runtime.ensure_current_room(
                db, self.groups, instance, self.geometry
            )
            self.assertIsNotNone(spawned)
            self.assertEqual(spawned["room_order"], order)
            replayed_spawn = dungeon_runtime.ensure_current_room(
                db, self.groups, instance, self.geometry
            )
            self.assertEqual(spawned["group_id"], replayed_spawn["group_id"])
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s AND room_order=%s",
                    (instance, order),
                ).fetchone()["n"],
            )
            fights = db.execute(
                "SELECT count(*) AS n FROM dungeon_room_encounters WHERE instance_id=%s AND room_order=%s",
                (instance, order),
            ).fetchone()["n"]
            self.assertEqual(fights, 0)
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            for member in members:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
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
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            result = dungeon_progression.settle_encounter(
                db, SimpleNamespace(id=fight_id, phase="finished", winner=0)
            )
            self.assertTrue(result["victory"])
            replay = dungeon_progression.settle_encounter(
                db, SimpleNamespace(id=fight_id, phase="finished", winner=0)
            )
            self.assertTrue(replay["replay"])
            return result

    def _gate_walk(self, binding):
        edges = {
            (tuple(a), tuple(b))
            for a, b in self.topology["exploration_geometry"]["edges"]
        }
        branch = next(
            b
            for b in self.topology["branch_routes"]
            if binding["source_id"] in b["physical_source_ids"]
        )
        source_room = branch["rooms"][binding["source_room"] - 1]
        source_cells = {tuple(c) for c in source_room["cells"]}
        destination_cells = {
            tuple(c) for c in branch["rooms"][binding["destination_room"] - 1]["cells"]
        }
        point = tuple(binding["position"])
        starts = sorted(a for a, b in edges if b == point and a in source_cells)
        ends = sorted(b for a, b in edges if a == point and b in destination_cells)
        self.assertTrue(
            starts and ends,
            f"Gate {binding['source_id']} needs literal native walk edges",
        )
        arrival = tuple(source_room["native_arrival"])
        queue, previous = [arrival], {arrival: None}
        for cell in queue:
            if cell in starts:
                break
            for a, b in edges:
                if a == cell and b in source_cells and b not in previous:
                    previous[b] = cell
                    queue.append(b)
        target = next((cell for cell in queue if cell in starts), None)
        self.assertIsNotNone(
            target, f"No native path from room {binding['source_room']} arrival to gate"
        )
        prefix, cell = [], target
        while cell is not None:
            prefix.append(cell)
            cell = previous[cell]
        prefix.reverse()
        path = tuple(prefix) + (point, ends[0])
        return dict(
            start_position=dict(zip(("x", "y", "z"), path[0])),
            end_position=dict(zip(("x", "y", "z"), path[-1])),
            steps=[
                dict(dx=b[0] - a[0], dy=b[1] - a[1], dz=b[2] - a[2])
                for a, b in zip(path, path[1:])
            ],
        )

    def test_both_durable_routes_gate_unselected_physical_branch_and_complete_cycle(
        self,
    ):
        branches = {b["key"]: b for b in self.topology["branch_routes"]}
        expected = {
            "route_34741": (34741, (34749, 34750)),
            "route_34740": (34740, (34751, 34752)),
        }
        evidence = []
        for branch_key, (entry_id, owned_gates) in expected.items():
            with self.subTest(branch=branch_key):
                members, party_id, instance = self._enter()
                with self.store.connection() as db:
                    self.assertIsNone(
                        dungeon_runtime.ensure_current_room(
                            db, self.groups, instance, self.geometry
                        )
                    )
                    self.assertIsNone(
                        db.execute(
                            "SELECT branch_key FROM dungeon_room_runs WHERE instance_id=%s",
                            (instance,),
                        ).fetchone()["branch_key"]
                    )
                    self.assertEqual(
                        0,
                        db.execute(
                            "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                            (instance,),
                        ).fetchone()["n"],
                    )
                    self.assertEqual(
                        0,
                        db.execute(
                            "SELECT count(*) AS n FROM combat_groups WHERE instance_id=%s",
                            (instance,),
                        ).fetchone()["n"],
                    )
                    self.assertEqual(
                        0,
                        db.execute(
                            "SELECT count(*) AS n FROM dungeon_transition_outbox WHERE instance_id=%s AND transition_kind='door'",
                            (instance,),
                        ).fetchone()["n"],
                    )

                # Failed encounter creation after durable selection rolls back choice and party travel.
                branch = branches[branch_key]
                selector = next(
                    d for d in self.topology["doors"] if d["source_id"] == entry_id
                )

                def fail_after_selection(db, instance_id):
                    dungeon_runtime.ensure_current_room(
                        db, self.groups, instance_id, self.geometry
                    )
                    raise RuntimeError("injected arrival failure")

                with self.assertRaisesRegex(RuntimeError, "injected arrival failure"):
                    self._door(
                        members, instance, entry_id, callback=fail_after_selection
                    )
                with self.store.connection() as db:
                    self.assertIsNone(
                        db.execute(
                            "SELECT branch_key FROM dungeon_room_runs WHERE instance_id=%s",
                            (instance,),
                        ).fetchone()["branch_key"]
                    )
                    self.assertEqual(
                        0,
                        db.execute(
                            "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                            (instance,),
                        ).fetchone()["n"],
                    )
                    self.assertEqual(
                        0,
                        db.execute(
                            "SELECT count(*) AS n FROM dungeon_transition_outbox WHERE instance_id=%s AND transition_kind='door'",
                            (instance,),
                        ).fetchone()["n"],
                    )
                    self.assertEqual(
                        1,
                        db.execute(
                            "SELECT revision FROM dungeon_instances WHERE instance_id=%s",
                            (instance,),
                        ).fetchone()["revision"],
                    )
                self._door(members, instance, entry_id)
                with self.store.connection() as db:
                    self.assertEqual(
                        branch_key,
                        db.execute(
                            "SELECT branch_key FROM dungeon_room_runs WHERE instance_id=%s",
                            (instance,),
                        ).fetchone()["branch_key"],
                    )
                    self.assertEqual(
                        1,
                        db.execute(
                            "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                            (instance,),
                        ).fetchone()["n"],
                    )
                for member in members:
                    actor = self.store.character(
                        member["account"], member["character"]["id"]
                    )
                    self.assertEqual(
                        tuple(actor[k] for k in ("x", "y", "z")),
                        tuple(selector["destination_position"]),
                    )

                # After selection, other branch transports/gates are unavailable even at their actual native approaches.
                other = next(b for k, b in branches.items() if k != branch_key)
                other_selector = next(
                    d
                    for d in self.topology["doors"]
                    if d["source_id"] == other["entry_source_id"]
                )
                self._place_party(
                    members, instance, other_selector["native_approach_cells"][0]
                )
                body = struct.pack(
                    ">qiBi",
                    other_selector["source_id"],
                    other_selector["destination_id"],
                    0,
                    2,
                )
                with self.assertRaisesRegex(ValueError, "different selected branch"):
                    dungeon_doors.advance(
                        self.store,
                        members[0]["account"],
                        members[0]["generation"],
                        members[0]["character"]["id"],
                        body,
                        source_allowed=lambda actor, source: source["id"]
                        == other_selector["source_id"]
                        and [actor[k] for k in ("x", "y", "z")]
                        in other_selector["native_approach_cells"],
                        room_for_position=self._room_for_position,
                        in_fight=lambda _id: False,
                        topology=self.topology,
                        on_arrival=lambda db, iid: dungeon_runtime.ensure_current_room(
                            db, self.groups, iid, self.geometry
                        ),
                    )
                selected_topology = dict(self.topology, selected_branch=branch_key)
                self.assertEqual(set(owned_gates), set(branch["physical_source_ids"]))
                blocked = dungeon_branches.unselected_gate_ids(selected_topology)
                self.assertEqual(set(other["physical_source_ids"]), set(blocked))
                packets = dungeon_native_flow.packets(
                    selected_topology,
                    map_id=self.route["start_map_id"],
                    instance_id=instance,
                    unlocked_room=1,
                )
                for gate_id in blocked:
                    packet = next(
                        body
                        for opcode, body in packets
                        if opcode == 12344
                        and struct.unpack_from(">q", body)[0] == gate_id
                    )
                    self.assertEqual(packet[17:19], b"\x00\x01")
                    self.assertEqual(packet[19:21], b"\x01\x00")

                # Each physical gate is closed until its preceding room receipt, and the chosen native branch remains pinned.
                chosen = branch["rooms"]
                for order in (1, 2):
                    binding = next(
                        g
                        for g in self.topology["physical_doors"]
                        if g["source_id"] in owned_gates and g["source_room"] == order
                    )
                    self.assertIn(
                        tuple(binding["position"]),
                        dungeon_branches.allowed_cells(selected_topology),
                    )
                    walk = self._gate_walk(binding)
                    with self.assertRaisesRegex(
                        ValueError, "locked room|locked room gate"
                    ):
                        dungeon_native_flow.validate_movement(
                            selected_topology, walk, unlocked_room=order
                        )
                    # Every route's alternate gate is closed even when its stage is current.
                    other_gate = next(
                        g
                        for g in self.topology["physical_doors"]
                        if g["source_id"] in other["physical_source_ids"]
                        and g["source_room"] == order
                    )
                    other_walk = self._gate_walk(other_gate)
                    with self.assertRaisesRegex(
                        ValueError, "locked room|locked room gate|outside unlocked"
                    ):
                        dungeon_native_flow.validate_movement(
                            selected_topology, other_walk, unlocked_room=order + 1
                        )
                    self._finish(members, party_id, instance, order)
                    with self.store.connection() as db:
                        progress = db.execute(
                            "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                            (instance,),
                        ).fetchone()["current_room"]
                    self.assertEqual(order + 1, progress)
                    # The native walking gate opens only after the receipt.
                    unlocked_blocked = dungeon_physical_doors.blocked_cells(
                        selected_topology, progress
                    )
                    self.assertNotIn(tuple(binding["position"]), unlocked_blocked)
                    self.assertEqual(
                        tuple(walk["end_position"][k] for k in ("x", "y", "z")),
                        dungeon_native_flow.validate_movement(
                            selected_topology, walk, unlocked_room=progress
                        ),
                    )
                    self._place_party(
                        members,
                        instance,
                        tuple(walk["end_position"][k] for k in ("x", "y", "z")),
                    )
                self._finish(members, party_id, instance, 3)
                # Branch-specific physical corridor reaches room three; route-specific final transport joins shared boss.
                advance_transport = next(
                    d
                    for d in self.topology["doors"]
                    if d["source_id"] == branch["source_ids"][1]
                )
                self._door(members, instance, advance_transport["source_id"])
                self._finish(members, party_id, instance, 4)
                # Complete boss return to shared lobby is the exact native transport, then native exterior exit.
                self._door(members, instance, 34746)
                exit_binding = self.topology["physical_exit_objects"][0]
                packets = dungeon_native_flow.packets(
                    selected_topology,
                    map_id=self.route["start_map_id"],
                    instance_id=instance,
                    unlocked_room=4,
                    completed=True,
                )
                source = generic_transports.source(
                    self.route["start_map_id"], exit_binding["source_id"]
                )
                self.assertIsNotNone(source)
                exit_packet = next(
                    payload
                    for opcode, payload in packets
                    if struct.unpack_from(">q", payload)[0] == exit_binding["source_id"]
                )
                self.assertEqual(exit_packet[19:21], b"\x01\x01")
                self._place_party(
                    members, instance, exit_binding["native_approach_cells"][0]
                )
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
                        source_allowed=lambda actor, candidate: candidate["id"]
                        == exit_binding["source_id"]
                        and [actor[k] for k in ("x", "y", "z")]
                        in exit_binding["native_approach_cells"],
                        in_fight=lambda _id: False,
                    )
                with self.store.connection() as db:
                    self.assertEqual(
                        "closed",
                        db.execute(
                            "SELECT status FROM dungeon_instances WHERE instance_id=%s",
                            (instance,),
                        ).fetchone()["status"],
                    )
                    self.assertEqual(
                        4,
                        db.execute(
                            "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                            (instance,),
                        ).fetchone()["n"],
                    )
                    self.assertEqual(
                        4,
                        db.execute(
                            "SELECT count(*) AS n FROM dungeon_room_encounters WHERE instance_id=%s AND status='victory'",
                            (instance,),
                        ).fetchone()["n"],
                    )
                    self.assertEqual(
                        18,
                        db.execute(
                            "SELECT count(*) AS n FROM dungeon_transition_outbox WHERE instance_id=%s AND transition_kind='door'",
                            (instance,),
                        ).fetchone()["n"],
                    )
                    revisions = db.execute(
                        "SELECT transition_revision,count(*) AS n FROM dungeon_transition_outbox WHERE instance_id=%s AND transition_kind='door' GROUP BY transition_revision ORDER BY transition_revision",
                        (instance,),
                    ).fetchall()
                    self.assertEqual([6, 6, 6], [row["n"] for row in revisions])
                evidence.append(
                    dict(
                        branch=branch_key,
                        selection=entry_id,
                        branch_physical_gates=list(owned_gates),
                        six_members=True,
                        rooms=4,
                        victory_receipts=4,
                        spawn_receipts=4,
                        native_boss_return=34746,
                        native_exit=34747,
                        rollback_verified=True,
                        opposite_route_blocked=True,
                    )
                )
        if os.environ.get("WAKFU_DUNGEON_LIFECYCLE_AUDIT"):
            hashes = {
                self.record["path"]: hashlib.sha256(self.config_bytes).hexdigest(),
                "candidate_report:docs/reports/dungeons/PALACIO-ZOLLO-NATIVE-CYCLE-CANDIDATE-V14-20261010.json": hashlib.sha256(
                    REPORT.read_bytes()
                ).hexdigest(),
            }
            for path in (
                "server/tests/test_zollo_branch_lifecycle_postgres.py",
                "server/local_game_server.py",
                "server/wakfu_server/maps/dungeon_branches.py",
                "server/wakfu_server/maps/dungeon_doors.py",
                "server/wakfu_server/maps/dungeon_native_flow.py",
                "server/wakfu_server/maps/dungeon_physical_doors.py",
                "server/wakfu_server/maps/dungeon_object_states.py",
                "server/wakfu_server/maps/dungeon_runtime.py",
                "server/wakfu_server/maps/dungeon_runtime_config.py",
                "server/wakfu_server/maps/dungeon_instances.py",
                "server/wakfu_server/maps/dungeon_transport.py",
                "server/wakfu_server/maps/dungeon_progression.py",
                "server/wakfu_server/maps/dungeon_room_spawns.py",
                "server/wakfu_server/maps/dungeon_exit.py",
            ):
                hashes[path] = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            output = Path(os.environ["WAKFU_DUNGEON_LIFECYCLE_AUDIT"])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(
                    dict(
                        scope="Isolated PostgreSQL six-member lifecycle, durable route choice, physical branch gates, shared final boss and native return; no spell/combat simulation",
                        runtime_activated=False,
                        candidate_config_file_sha256=hashlib.sha256(
                            self.config_bytes
                        ).hexdigest(),
                        candidate_config_canonical_sha256=dungeon_runtime_config.canonical_hash(
                            self.source_config
                        ),
                        candidate_evidence_hashes=self.source_config["evidence_hashes"],
                        source_sha256=hashes,
                        records=evidence,
                    ),
                    indent=2,
                )
                + "\n"
            )

    def test_lobby_exit_cancels_run_without_selecting_or_spawning(self):
        members, _party_id, instance = self._enter()
        exit_binding = self.topology["physical_exit_objects"][0]
        self._place_party(members, instance, exit_binding["native_approach_cells"][0])
        packets = dungeon_native_flow.packets(
            self.topology,
            map_id=self.route["start_map_id"],
            instance_id=instance,
            unlocked_room=1,
            completed=False,
        )
        body = next(
            payload
            for opcode, payload in packets
            if struct.unpack_from(">q", payload)[0] == exit_binding["source_id"]
        )
        self.assertEqual(body[19:21], b"\x01\x01")
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
                source_allowed=lambda actor, source: source["id"]
                == exit_binding["source_id"]
                and [actor[k] for k in ("x", "y", "z")]
                in exit_binding["native_approach_cells"],
                in_fight=lambda _id: False,
            )
        with self.store.connection() as db:
            progress = db.execute(
                "SELECT branch_key,current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
                (instance,),
            ).fetchone()
            self.assertIsNone(progress["branch_key"])
            self.assertEqual(1, progress["current_room"])
            self.assertEqual("active", progress["status"])
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["n"],
            )
            self.assertEqual(
                "closed",
                db.execute(
                    "SELECT status FROM dungeon_instances WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["status"],
            )


del Fixture
