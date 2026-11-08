"""Reproduction graphs preserve native data identity instead of JSON guesses."""
import json
import unittest

from wakfu_server.combat_reproduction_state import (
    encode_state,
    decode_state,
    UnsupportedReproductionState,
)
from wakfu_server.combat_reproduction_graph_compare import compare_graphs


class ReproductionStateTests(unittest.TestCase):
    def roundtrip(self, value):
        return decode_state(json.loads(json.dumps(encode_state(value))))

    def test_preserves_key_types_order_bytes_and_shared_references(self):
        shared = [b"\x00\xff", (1, 2, 3), frozenset({9, 2})]
        before = {7: shared, "7": shared, (8, 9): {3, 1}, "empty": {}, "unknown": None}
        after = self.roundtrip(before)
        self.assertEqual(list(after), list(before))
        self.assertEqual(after, before)
        self.assertIs(after[7], after["7"])
        self.assertIsInstance(after[7][1], tuple)
        self.assertIsInstance(after[7][2], frozenset)

    def test_preserves_mutable_cycle_without_pickle(self):
        values = []
        root = {"values": values}
        values.append(root)
        after = self.roundtrip(root)
        self.assertIs(after["values"][0], after)

    def test_unknown_callbacks_types_schema_and_references_reject(self):
        for value in (lambda: 1, unittest.TestCase(), float("nan")):
            with self.assertRaises(UnsupportedReproductionState):
                encode_state(value)
        for payload in (
            {"schema": "pickle"},
            dict(
                schema="wakemu-combat-reproduction-state-v1",
                root={"ref": -1},
                nodes=[],
                services=[],
            ),
            dict(
                schema="wakemu-combat-reproduction-state-v1",
                root={"ref": 0},
                nodes=[{"kind": "object", "type": "os.system"}],
                services=[],
            ),
        ):
            with self.assertRaises(UnsupportedReproductionState):
                decode_state(payload)

    def test_preserves_database_temporal_values_and_fixed_timezone_identity(self):
        import datetime

        zone = datetime.timezone(datetime.timedelta(hours=-5), "America/Bogota")
        stamp = datetime.datetime(2026, 11, 8, 12, 34, 56, 123456, tzinfo=zone, fold=1)
        source = {
            "created_at": stamp,
            "same_stamp": stamp,
            "date": datetime.date(2026, 11, 8),
            "time": datetime.time(12, 34, 56, 654321, tzinfo=zone, fold=1),
            "duration": datetime.timedelta(days=2, seconds=3, microseconds=4),
            "utc_singleton": datetime.timezone.utc,
            "named_utc": datetime.timezone(datetime.timedelta(0), "UTC"),
        }
        restored = self.roundtrip(source)
        self.assertEqual(restored, source)
        self.assertIs(restored["created_at"], restored["same_stamp"])
        self.assertIs(restored["created_at"].tzinfo, restored["time"].tzinfo)
        self.assertEqual(restored["created_at"].fold, 1)
        self.assertEqual(
            restored["created_at"].utcoffset(), datetime.timedelta(hours=-5)
        )
        self.assertEqual(restored["created_at"].tzname(), "America/Bogota")
        self.assertIs(restored["utc_singleton"], datetime.timezone.utc)
        self.assertIsNot(restored["named_utc"], datetime.timezone.utc)
        self.assertEqual(restored["named_utc"].tzname(None), "UTC")

    def test_graph_comparator_validates_temporal_nodes_and_timezone_aliases(self):
        import datetime

        zone = datetime.timezone(datetime.timedelta(hours=-5), "America/Bogota")
        source = {
            "created_at": datetime.datetime(
                2026, 11, 8, 12, 34, 56, tzinfo=zone, fold=1
            ),
            "time": datetime.time(12, 34, 56, tzinfo=zone, fold=1),
            "date": datetime.date(2026, 11, 8),
            "duration": datetime.timedelta(days=1, seconds=2),
            "zone": zone,
            "utc": datetime.timezone.utc,
        }
        before = encode_state(source, preserve_scalars=True)
        restored = decode_state(before)
        after = encode_state(restored, preserve_scalars=True)
        self.assertTrue(compare_graphs(before, before))
        self.assertTrue(compare_graphs(before, after))
        changed = dict(source)
        changed["created_at"] = source["created_at"].replace(fold=0)
        self.assertFalse(
            compare_graphs(before, encode_state(changed, preserve_scalars=True))
        )

    def test_party_publication_lease_roundtrips_six_owner_aliases_and_invalidation(
        self,
    ):
        import struct
        from wakfu_server.combat_instance_publication import (
            InstancePublicationTracker,
            PartyPublicationLease,
            bind_party_encounter,
            require_current_publication,
        )
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.maps.proto_dungeon import encode as encode_proto

        owner_ids = tuple(range(101, 107))
        players = [
            Actor(
                owner_id,
                0,
                (index, 0, 0),
                60,
                6,
                3,
                10,
                1,
                owner_id=owner_id,
                controlled=True,
            )
            for index, owner_id in enumerate(owner_ids)
        ]
        npc = Actor(-99, 1, (7, 0, 0), 40, 6, 3, 5, 1)
        actors = {actor.id: actor for actor in (*players, npc)}
        fight = Fight(
            778,
            tuple(actors.values()),
            {actor.position for actor in actors.values()},
            {0: {actor.position for actor in players}, 1: {npc.position}},
        )
        context = encode_proto({"difficulty_level": 2})
        frame_payload = b"".join(
            struct.pack(">H", len(part)) + part
            for part in (b"party-fixture", b"", b"\0\0", context)
        )
        frame = struct.pack(">IH", 6 + len(frame_payload), 13974) + frame_payload
        publications = []
        for owner_id in owner_ids:
            scope = (owner_id, f"owner-generation-{owner_id}", owner_id, 1, 0)
            tracker = InstancePublicationTracker()
            tracker.after_write(frame, scope)
            # A previously bound single-owner encounter leaves this alias on
            # the shared lease when the tracker is later admitted to a party.
            tracker.lease.owner_bindings = ((tracker, scope),)
            publications.append((tracker, scope))
        self.assertTrue(
            bind_party_encounter(
                fight, publications=tuple(publications), npc_ids=(npc.id,)
            )
        )
        require_current_publication(fight)

        restored = self.roundtrip({"fight": fight})["fight"]
        lease = restored.native_instance_publication_lease
        self.assertIs(type(lease), PartyPublicationLease)
        self.assertEqual(len(lease.leases), 6)
        require_current_publication(restored)
        for index, (tracker, scope) in enumerate(lease.owner_bindings):
            self.assertIs(type(tracker), InstancePublicationTracker)
            self.assertIs(tracker.lease, lease.leases[index])
            self.assertIs(tracker.scope, scope)
            self.assertIs(lease.leases[index].owner_bindings[0][0], tracker)
            self.assertIs(lease.leases[index].owner_bindings[0][1], scope)
            self.assertEqual(tracker.published.sha256, lease.leases[index].current[3])
        self.assertEqual(
            restored.native_instance_publication_receipt,
            tuple(lease.current),
        )
        stale_tracker, stale_scope = lease.owner_bindings[2]
        stale_tracker.synchronize(
            (
                stale_scope[0],
                stale_scope[1] + "-rotated",
                stale_scope[2],
                stale_scope[3],
                stale_scope[4],
            )
        )
        self.assertIsNone(lease.current)
        self.assertIsNot(stale_tracker.scope, stale_scope)
        self.assertIs(lease.leases[2].owner_bindings[0][1], stale_scope)
        with self.assertRaises(ValueError):
            require_current_publication(restored)
        require_current_publication(fight)

    def test_rejects_nonstandard_timezone_provider(self):
        import datetime

        class CustomTimezone(datetime.tzinfo):
            def utcoffset(self, value):
                return datetime.timedelta(0)

        with self.assertRaisesRegex(
            UnsupportedReproductionState, "Unsupported reproduction type"
        ):
            encode_state(datetime.datetime(2026, 11, 8, tzinfo=CustomTimezone()))

    def test_duplicate_mapping_keys_are_rejected(self):
        payload = encode_state({1: "a"})
        payload["nodes"][0]["items"].append([1, "b"])
        with self.assertRaisesRegex(UnsupportedReproductionState, "Duplicate"):
            decode_state(payload)

    def test_synthetic_attribute_dicts_cannot_alias_through_reused_python_ids(self):
        from wakfu_server.combat_state_timing import StateTimer

        timers = [StateTimer(index, index + 1, "start") for index in range(100)]
        payload = encode_state(timers)
        attributes = [
            node["attrs"]["ref"]
            for node in payload["nodes"]
            if node.get("type") == "StateTimer"
        ]
        self.assertEqual(len(set(attributes)), 100)
        self.assertEqual(decode_state(payload), timers)

    def test_runtime_pending_and_typed_state_are_not_lost(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_state_ledger import RunningState
        from wakfu_server.combat_state_timing import StateTimer
        from wakfu_server.combat_geometry_snapshot import freeze_terrain

        pc = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        fight = Fight(
            77,
            (pc, npc),
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        freeze_terrain(fight)
        state = RunningState(
            9,
            12,
            1,
            7,
            -7,
            2,
            "caster",
            False,
            (123,),
            0,
            True,
            StateTimer(7, 3, "start"),
        )
        npc.state_ledger._entries = (state,)
        runtime = RuntimeMessages(fight, clock=lambda: 5)
        runtime.pending = [(12613, b"pending bytes")]
        runtime.awaiting_ack = 4
        runtime.native_action_id = 13
        after = self.roundtrip(runtime)
        self.assertEqual(after.pending, runtime.pending)
        self.assertEqual(after.awaiting_ack, 4)
        self.assertEqual(after.native_action_id, 13)
        self.assertEqual(after.fight.actors[-7].state_ledger.entries, (state,))
        self.assertIsInstance(after.fight.walkable, frozenset)
        self.assertIsNone(after.clock)
        self.assertEqual(encode_state(after)["nodes"], encode_state(runtime)["nodes"])

    def test_characteristic_listener_keeps_exact_fight_owner(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_characteristic_link import (
            ObservableCharacteristicStats,
        )

        pc = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        fight = Fight(
            77,
            (pc, npc),
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        pc.effect_stats = ObservableCharacteristicStats({20: 15}, fight, 7)
        restored = self.roundtrip(fight)
        self.assertIs(restored.actors[7].effect_stats._fight, restored)
        self.assertEqual(dict(restored.actors[7].effect_stats), {20: 15})

    def test_canonical_pointer_topology_keeps_actual_actor_identity(self):
        from wakfu_server.combat_state import Actor, Fight
        from native_combat_fixture import initialize_fixture_qi
        from wakfu_server.combat_pointer_qi_actor import ActualActorQI
        from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint

        pc = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        fight = Fight(
            77,
            (pc, npc),
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        initialize_fixture_qi(fight)
        qi = ActualActorQI(fight)
        fight.native_pointer_checkpoint = NativePointerCheckpoint(qi)
        qi.remove(qi.objects[-7])
        fight.native_pointer_checkpoint.publish()
        restored = self.roundtrip(fight)
        owner = restored.native_pointer_checkpoint.validate(restored)
        self.assertIs(owner.objects[7].actor, restored.actors[7])
        self.assertIs(owner.objects[-7].actor, restored.actors[-7])
        self.assertEqual(restored.actors[-7].native_obstacle_id, -1)
        self.assertEqual(
            dict(restored.native_pointer_checkpoint),
            dict(fight.native_pointer_checkpoint),
        )


if __name__ == "__main__":
    unittest.main()
