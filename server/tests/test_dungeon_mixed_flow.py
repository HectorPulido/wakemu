"""Mixed native traversal keeps intra-room transports separate from progress."""
import copy
import struct
import unittest
from unittest.mock import patch

from wakfu_server import dungeon_doors, dungeon_native_flow, dungeon_physical_doors


class MixedNativeFlowTests(unittest.TestCase):
    def setUp(self):
        self.source = dict(
            map_id=9,
            id=20,
            x=2,
            y=0,
            z=0,
            approach_positions=[],
            approach_blocks_center=False,
            destinations=[
                dict(
                    destination_id=30,
                    map_id=9,
                    x=4,
                    y=0,
                    z=0,
                    criterion="",
                    cyZ=-1,
                    cyX=0,
                    cyW=0,
                    item_reference=0,
                    native_altitude_walkable=True,
                )
            ],
        )
        self.topology = dict(
            policy=dungeon_native_flow.MIXED_POLICY,
            asset_map_id=9,
            rooms=[
                dict(order=1, anchor=[0, 0, 0], cells=[[0, 0, 0]]),
                dict(order=2, anchor=[2, 0, 0], cells=[[2, 0, 0], [4, 0, 0]]),
            ],
            physical_doors=[
                dict(
                    source_id=10, source_room=1, destination_room=2, position=[1, 0, 0]
                )
            ],
            physical_exit_objects=[],
            doors=[
                dict(
                    source_id=20,
                    destination_id=30,
                    source_room=2,
                    destination_room=2,
                    source_position=[2, 0, 0],
                    native_approach_cells=[[2, 0, 0]],
                    destination_position=[4, 0, 0],
                )
            ],
            exploration_geometry=dict(
                cells=[[0, 0, 0], [1, 0, 0], [2, 0, 0], [4, 0, 0]],
                edges=[([0, 0, 0], [1, 0, 0]), ([1, 0, 0], [2, 0, 0])],
            ),
        )
        self.character = dict(map_id=9, instance_id=99)
        self.body = struct.pack(">qiBi", 20, 30, 0, 2)
        self.native = patch(
            "wakfu_server.generic_transports.source", return_value=self.source
        )
        self.native.start()
        self.addCleanup(self.native.stop)

    def resolve(self, **overrides):
        return dungeon_doors.resolve(
            self.character,
            self.body,
            source_allowed=lambda c, s: True,
            room_for_position=lambda m, x, y, z: 2,
            criterion_allowed=lambda c: True,
            topology=overrides.get("topology", self.topology),
        )

    def test_same_stage_teleport_requires_exact_mixed_binding(self):
        self.assertEqual(self.resolve()[:2], (2, 2))
        for mutation in ("binding", "arrival", "policy"):
            t = copy.deepcopy(self.topology)
            if mutation == "binding":
                t["doors"] = []
            elif mutation == "arrival":
                t["doors"][0]["destination_position"] = [5, 0, 0]
            else:
                t["policy"] = dungeon_native_flow.TELEPORT_POLICY
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.resolve(topology=t)

    def test_packets_include_closed_gate_and_locked_intra_transport(self):
        with patch("wakfu_server.generic_transports._CATALOG", [self.source]):
            closed = dungeon_native_flow.packets(
                self.topology, map_id=9, instance_id=99, unlocked_room=1
            )
            opened = dungeon_native_flow.packets(
                self.topology, map_id=9, instance_id=99, unlocked_room=2
            )
        by_id = lambda rows: {
            struct.unpack_from(">q", body)[0]: body for _, body in rows
        }
        self.assertEqual(set(by_id(closed)), {10, 20})
        self.assertEqual(by_id(closed)[20][20], 0)
        self.assertEqual(by_id(opened)[20][20], 1)
        self.assertEqual(by_id(closed)[10][19], 1)
        self.assertEqual(by_id(opened)[10][19], 0)

    def test_physical_gate_cannot_be_crossed_until_committed_frontier(self):
        request = dict(
            start_position=dict(x=0, y=0, z=0),
            end_position=dict(x=2, y=0, z=0),
            steps=[dict(dx=1, dy=0, dz=0), dict(dx=1, dy=0, dz=0)],
        )
        with self.assertRaises(ValueError):
            dungeon_native_flow.validate_movement(
                self.topology, request, unlocked_room=1
            )
        dungeon_native_flow.validate_movement(self.topology, request, unlocked_room=2)

    def test_native_teleport_does_not_authorize_non_native_walking(self):
        request = dict(
            start_position=dict(x=2, y=0, z=0), steps=[dict(dx=2, dy=0, dz=0)]
        )
        with self.assertRaises(ValueError):
            dungeon_native_flow.validate_movement(
                self.topology, request, unlocked_room=2
            )


from postgres_case import PostgresCase
from test_dungeon_doors import DungeonDoorProgressionTests as _DoorFixture
from types import SimpleNamespace
from wakfu_server.maps.dungeon_progression import initialize_run


class MixedNativeTransactionTests(PostgresCase):
    install_context_policy = _DoorFixture.install_context_policy
    player = _DoorFixture.player
    party = _DoorFixture.party
    enter = _DoorFixture.enter

    def setUp(self):
        PostgresCase.setUp(self)
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)
        self.members, self.party_id = self.party(2)
        self.instance = self.enter(self.members[0])
        self.instance_id = self.instance["instance_id"]
        monster = SimpleNamespace(
            ref_id=1, count=1, native_min_level=1, native_max_level=5, role="monster"
        )
        plan = SimpleNamespace(
            roster_ready=True,
            document_sha256="b" * 64,
            rooms=tuple(
                SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
            ),
        )
        with self.store.connection() as db:
            initialize_run(db, self.instance_id, self.party_id, plan)

    def transport(self, *, room=1, fighting=False):
        source = dict(
            map_id=1086,
            id=901,
            x=4,
            y=-12,
            z=0,
            approach_positions=[],
            approach_blocks_center=False,
            destinations=[
                dict(
                    destination_id=902,
                    map_id=1086,
                    x=8,
                    y=-12,
                    z=0,
                    criterion="",
                    cyZ=-1,
                    cyX=0,
                    cyW=0,
                    item_reference=0,
                    native_altitude_walkable=True,
                )
            ],
        )
        topology = dict(
            policy=dungeon_native_flow.MIXED_POLICY,
            asset_map_id=1086,
            rooms=[dict(order=room, cells=[[4, -12, 0], [8, -12, 0]])],
            doors=[
                dict(
                    source_id=901,
                    destination_id=902,
                    source_room=room,
                    destination_room=room,
                    source_position=[4, -12, 0],
                    native_approach_cells=[[4, -12, 0]],
                    destination_position=[8, -12, 0],
                )
            ],
        )
        with patch("wakfu_server.generic_transports.source", return_value=source):
            return dungeon_doors.advance(
                self.store,
                self.members[0]["account"],
                self.members[0]["generation"],
                self.members[0]["character"]["id"],
                struct.pack(">qiBi", 901, 902, 0, 2),
                source_allowed=lambda c, s: True,
                room_for_position=lambda *p: room,
                in_fight=lambda c: fighting,
                topology=topology,
            )

    def test_intra_stage_party_transport_is_atomic_without_advancing_progress(self):
        result = self.transport()
        self.assertEqual(len(result["members"]), 2)
        with self.store.connection() as db:
            progress = db.execute(
                "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()
            self.assertEqual(progress["current_room"], 1)
            self.assertEqual(progress["status"], "active")
            rows = db.execute(
                "SELECT destination_x,transition_kind FROM dungeon_transition_outbox "
                "WHERE instance_id=%s AND status='pending'",
                (self.instance_id,),
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertTrue(
                all(
                    r["destination_x"] == 8 and r["transition_kind"] == "door"
                    for r in rows
                )
            )
        for member in self.members:
            actor = self.store.character(member["account"], member["character"]["id"])
            self.assertEqual(
                (actor["x"], actor["y"], actor["instance_id"]),
                (8, -12, self.instance_id),
            )

    def test_intra_transport_cannot_enter_locked_stage_or_move_fighting_party(self):
        for kwargs in (dict(room=2), dict(fighting=True)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.transport(**kwargs)
        for member in self.members:
            actor = self.store.character(member["account"], member["character"]["id"])
            self.assertEqual((actor["x"], actor["y"]), (4, -12))


# Imported fixture methods are captured above; do not discover its test class here.
del _DoorFixture


class ExplicitNativeExclusionTests(unittest.TestCase):
    setUp = MixedNativeFlowTests.setUp

    def excluded(self):
        from wakfu_server.dungeon_runtime_config import canonical_hash

        source = copy.deepcopy(self.source)
        source.update(id=90, x=99)
        source["destinations"][0].update(map_id=71)
        self.topology["disabled_native_sources"] = [
            dict(
                source_id=90,
                reason="Native optional annex is outside the reviewed main encounter route",
                source_sha256=canonical_hash(source),
            )
        ]
        return source

    def test_exact_unbound_optional_source_is_hidden_and_rejected(self):
        source = self.excluded()
        with patch(
            "wakfu_server.generic_transports._CATALOG", [self.source, source]
        ), patch("wakfu_server.generic_transports.source", return_value=source):
            rows = dungeon_native_flow.packets(
                self.topology, map_id=9, instance_id=99, unlocked_room=2
            )
            body = next(
                body for _, body in rows if struct.unpack_from(">q", body)[0] == 90
            )
            self.assertEqual((body[19], body[20]), (0, 0))
            with self.assertRaisesRegex(ValueError, "explicitly excluded"):
                dungeon_doors.resolve(
                    self.character,
                    struct.pack(">qiBi", 90, 30, 0, 2),
                    source_allowed=lambda c, s: True,
                    room_for_position=lambda *p: 2,
                    criterion_allowed=lambda c: True,
                    topology=self.topology,
                )

    def test_mandatory_path_overlap_and_stale_catalog_hash_fail_closed(self):
        source = self.excluded()
        for mutation in ("door", "exit", "gate", "hash", "reason", "duplicate"):
            t = copy.deepcopy(self.topology)
            record = t["disabled_native_sources"][0]
            if mutation in ("door", "exit", "gate"):
                key = {
                    "door": "doors",
                    "exit": "physical_exit_objects",
                    "gate": "physical_doors",
                }[mutation]
                t[key].append(dict(source_id=90))
            elif mutation == "hash":
                record["source_sha256"] = "0" * 64
            elif mutation == "reason":
                record["reason"] = " "
            else:
                t["disabled_native_sources"].append(copy.deepcopy(record))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                dungeon_native_flow.disabled_source_ids(t, [self.source, source])

    def test_exclusions_cannot_be_applied_to_other_policy_or_foreign_catalog_map(self):
        source = self.excluded()
        t = copy.deepcopy(self.topology)
        t["policy"] = dungeon_native_flow.TELEPORT_POLICY
        with self.assertRaises(ValueError):
            dungeon_native_flow.disabled_source_ids(t, [source])
        source["map_id"] = 999
        with self.assertRaises(ValueError):
            dungeon_native_flow.disabled_source_ids(self.topology, [source])
