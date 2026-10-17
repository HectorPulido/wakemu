"""Reproduction graphs preserve native data identity instead of JSON guesses."""
import json
import unittest

from wakfu_server.combat_reproduction_state import (
    encode_state,
    decode_state,
    UnsupportedReproductionState,
)


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
