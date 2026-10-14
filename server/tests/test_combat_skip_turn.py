"""Live native SKIP_TURN uses ordinary runtime expiry and ACK progression."""
import struct
import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_skip_turn import skip_turn_required


class SkipTurnTests(unittest.TestCase):
    def fixture(self, both=False, controlled=False):
        first = Actor(-200, 1, (0, 0, 0), 100, 6, 3, 20, 1, 3, controlled)
        other = Actor(7, 0, (1, 0, 0), 100, 6, 3, 10, 1, 3, True)
        fight = Fight(
            78, [first, other], {(0, 0, 0), (1, 0, 0)}, {1: {(0, 0, 0)}, 0: {(1, 0, 0)}}
        )
        fight.ready(3)
        first.native_fight_property_counts = {1: 1, 15: 1}
        first.native_fight_properties = frozenset({1, 15})
        if both:
            other.native_fight_property_counts = {1: 1}
            other.native_fight_properties = frozenset({1})
        return fight, first, other

    def test_npc_turn_skips_once_and_waits_for_actual_ack(self):
        fight, first, other = self.fixture()
        runtime = RuntimeMessages(fight)
        packets = runtime.turn_started()
        self.assertIs(fight.current, other)
        self.assertEqual(runtime.awaiting_ack, 1)
        self.assertTrue(any(opcode == 12502 for opcode, _ in packets))
        self.assertEqual(sum(e["kind"] == "turn_skipped" for e in fight.events), 1)
        self.assertEqual(first.native_fight_property_counts, {1: 1, 15: 1})
        runtime.acknowledge_turn(struct.pack(">i", 1))
        self.assertIsNone(runtime.awaiting_ack)
        self.assertEqual(fight.turn_id, 2)

    def test_controlled_actor_uses_its_original_owner_turn_api(self):
        fight, first, other = self.fixture(controlled=True)
        runtime = RuntimeMessages(fight)
        runtime.turn_started()
        self.assertIs(fight.current, other)
        self.assertEqual(runtime.awaiting_ack, 1)

    def test_consecutive_skips_are_ack_bounded_and_expiry_owns_property(self):
        fight, first, other = self.fixture(both=True)
        runtime = RuntimeMessages(fight)
        runtime.turn_started()
        self.assertEqual(fight.turn_id, 2)
        runtime.acknowledge_turn(struct.pack(">i", 1))
        self.assertEqual(fight.turn_id, 3)
        self.assertEqual(runtime.awaiting_ack, 2)
        # Model normal native removal before the next registered start delivery.
        first.native_fight_property_counts = {15: 1}
        first.native_fight_properties = frozenset({15})
        runtime.acknowledge_turn(struct.pack(">i", 2))
        self.assertIsNone(runtime.awaiting_ack)
        self.assertEqual(fight.turn_id, 3)
        self.assertFalse(skip_turn_required(first))

    def test_zero_property_count_does_not_skip(self):
        fight, first, _ = self.fixture()
        first.native_fight_property_counts = {1: 0}
        runtime = RuntimeMessages(fight)
        runtime.turn_started()
        self.assertEqual(fight.turn_id, 1)
        self.assertIsNone(runtime.awaiting_ack)
