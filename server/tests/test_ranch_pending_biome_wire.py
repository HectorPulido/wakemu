"""Pending fBU rows share the original scene and component18 serializer."""
import struct
import unittest

from wakfu_server import haven_ranch_furniture_wire as wire
from wakfu_server import ranch_reward_retrieval as rewards


def reward(**overrides):
    row = dict(
        uid=41,
        reference=2021,
        quantity=2,
        monster_uid=57,
        drop_date_ms=1234567,
        retrieved=False,
    )
    return dict(row, **overrides)


class RanchPendingBiomeWireTests(unittest.TestCase):
    def test_empty_publication_keeps_the_native_empty_reward_tail(self):
        legacy_empty = wire.biome_record([1], [], 1234567)
        pending_empty = wire.biome_record([1], [], 1234567, rewards=[])
        self.assertEqual(pending_empty, legacy_empty)
        self.assertEqual(pending_empty[-12:], struct.pack(">iq", 0, 1234567))

    def test_pending_and_retrieved_rewards_publish_sorted_complete_native_rows(self):
        rows = [reward(uid=42, retrieved=True), reward()]
        scene = wire.biome_record([1], [], 1234567, rewards=rows)
        expected_tail = (
            struct.pack(">i", 2)
            + rewards.encode_reward(rows[1])
            + rewards.encode_reward(rows[0])
            + struct.pack(">q", 1234567)
        )
        self.assertEqual(scene[-len(expected_tail) :], expected_tail)
        opcode, context = wire.context(11, 1440, [1], [], 1234567, rewards=rows)
        self.assertEqual(
            (opcode, context), (13864, struct.pack(">qqB", 11, 1440, 1) + scene)
        )

    def test_invalid_or_duplicate_fbu_rows_are_rejected_before_publication(self):
        for bad in (None, {}, iter(())):
            with self.subTest(collection=bad), self.assertRaises(ValueError):
                wire.biome_record([1], [], 1, rewards=bad)
        with self.assertRaises(ValueError):
            wire.biome_record([1], [], 1, rewards=[reward(), reward()])
        for key, value in (
            ("uid", 0),
            ("uid", 2**63),
            ("reference", 0),
            ("reference", 2**31),
            ("quantity", 0),
            ("quantity", 32768),
            ("monster_uid", 0),
            ("monster_uid", 2**63),
            ("drop_date_ms", -1),
            ("drop_date_ms", 2**63),
            ("retrieved", 1),
        ):
            with self.subTest(field=key, value=value), self.assertRaises(
                (ValueError, struct.error)
            ):
                wire.biome_record([1], [], 1, rewards=[reward(**{key: value})])


if __name__ == "__main__":
    unittest.main()
