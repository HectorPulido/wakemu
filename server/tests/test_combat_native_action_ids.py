import struct
import unittest
from types import SimpleNamespace
from wakfu_server.combat_native_action_ids import (
    MAX_NATIVE_ACTION_ID,
    NATIVE_ACTION_PACKETS,
    prepare_native_delivery,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages


class NativeActionIdTests(unittest.TestCase):
    def block(self):
        header = struct.pack(">iii", 91, 228, -1)
        return [
            (13509, header + b"animation"),
            (12613, header + b"uid-and-state-payload"),
            (13420, struct.pack(">i", 91)),
            (12873, b"full-actor-stats"),
            (13510, struct.pack(">i", 13)),
        ]

    def test_original_packet_registry_distinguishes_ack_flush_and_world_movement(self):
        self.assertTrue(
            {12588, 12678, 12613, 13497, 13560, 13509} <= NATIVE_ACTION_PACKETS
        )
        self.assertTrue({13420, 13510, 12873, 13852}.isdisjoint(NATIVE_ACTION_PACKETS))

    def test_orientation_and_abandon_are_numbered_without_changing_their_bodies(self):
        header = struct.pack(">iii", 91, 228, -1)
        original = [
            (13494, header + b"orientation-body"),
            (12238, header + b"losers-and-winners"),
        ]
        packets, last = prepare_native_delivery(original, fight_id=91, previous_id=72)
        self.assertEqual(last, 74)
        self.assertEqual(
            [a["native_action_id"] for a in packets.native_actions], [73, 74]
        )
        self.assertEqual(
            [body[12:] for _, body in packets], [body[12:] for _, body in original]
        )

    def test_unique_actions_preserve_payload_identity_and_turn_ack(self):
        original = self.block()
        packets, last = prepare_native_delivery(original, fight_id=91, previous_id=70)
        self.assertEqual(last, 72)
        self.assertEqual(
            [struct.unpack_from(">i", b, 4)[0] for _, b in packets[:2]], [71, 72]
        )
        self.assertEqual(
            [b[8:] for _, b in packets[:2]], [b[8:] for _, b in original[:2]]
        )
        self.assertEqual(packets[2:], tuple(original[2:]))
        self.assertEqual(
            [x["request_action_id"] for x in packets.native_actions], [228, 228]
        )
        self.assertEqual(original, self.block())

    def test_prepared_delivery_is_not_renumbered_at_second_boundary(self):
        wire = RuntimeMessages(SimpleNamespace(id=91))
        packets = wire.prepare_delivery(self.block())
        again = wire.prepare_delivery(packets)
        self.assertIs(again, packets)
        self.assertEqual(wire.native_action_id, 2)
        self.assertEqual(wire.action_id, 0)

    def test_validation_failure_preserves_runtime_counter_and_authoritative_hp(self):
        fight = SimpleNamespace(id=91, hp=86)
        wire = RuntimeMessages(fight)
        malformed = self.block() + [(12613, struct.pack(">iii", 92, 228, -1))]
        with self.assertRaisesRegex(ValueError, "another fight"):
            wire.prepare_delivery(malformed)
        self.assertEqual((wire.native_action_id, fight.hp), (0, 86))

    def test_exhaustion_does_not_wrap_or_partially_publish(self):
        wire = RuntimeMessages(SimpleNamespace(id=91))
        wire.native_action_id = MAX_NATIVE_ACTION_ID - 1
        with self.assertRaisesRegex(ValueError, "exhausted"):
            wire.prepare_delivery(self.block())
        self.assertEqual(wire.native_action_id, MAX_NATIVE_ACTION_ID - 1)
        final = wire.prepare_delivery(self.block()[:1])
        self.assertEqual(
            final.native_actions[0]["native_action_id"], MAX_NATIVE_ACTION_ID
        )
        with self.assertRaisesRegex(ValueError, "exhausted"):
            wire.prepare_delivery(self.block()[:1])

    def test_invalid_start_and_truncated_packet_reject(self):
        for previous in (None, True, -1, 1 << 31):
            with self.assertRaises(ValueError):
                prepare_native_delivery(self.block(), fight_id=91, previous_id=previous)
        with self.assertRaisesRegex(ValueError, "Truncated"):
            prepare_native_delivery([(12613, b"short")], fight_id=91, previous_id=0)


class NativeTurnDeliveryTests(unittest.TestCase):
    def runtime(self):
        from wakfu_server.combat_state import Actor, Fight

        cells = {(0, 0, 0), (1, 0, 0)}
        fight = Fight(
            7,
            [
                Actor(100, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, (1, 0, 0), 20, 4, 2, 10, 1),
            ],
            cells,
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.ready(1)
        return RuntimeMessages(fight)

    def test_pending_next_turn_is_numbered_only_after_exact_turn_ack(self):
        runtime = self.runtime()
        delivered = runtime.end_turn(1, 100, 1)
        self.assertEqual(runtime.native_action_id, 1)
        self.assertEqual(runtime.awaiting_ack, 1)
        self.assertIsInstance(runtime.pending, list)
        raw = tuple(runtime.pending)
        with self.assertRaises(ValueError):
            runtime.acknowledge_turn(struct.pack(">i", 99))
        self.assertEqual(tuple(runtime.pending), raw)
        self.assertEqual(runtime.native_action_id, 1)
        next_turn = runtime.acknowledge_turn(struct.pack(">i", 1))
        ids = [x["native_action_id"] for x in next_turn.native_actions]
        self.assertEqual(ids, [2, 3, 4])
        self.assertIs(runtime.prepare_delivery(next_turn), next_turn)
        self.assertEqual(runtime.native_action_id, 4)
        self.assertEqual(runtime.pending, [])
        self.assertEqual(runtime.fight.current.id, -200)

    def test_exhaustion_rolls_back_turn_advance_and_pending_ack(self):
        runtime = self.runtime()
        runtime.native_action_id = MAX_NATIVE_ACTION_ID
        with self.assertRaisesRegex(ValueError, "exhausted"):
            runtime.end_turn(1, 100, 1)
        self.assertEqual(runtime.fight.turn_id, 1)
        self.assertEqual(runtime.fight.current.id, 100)
        self.assertIsNone(runtime.awaiting_ack)
        self.assertEqual(runtime.pending, [])
        self.assertEqual(runtime.action_id, 0)
