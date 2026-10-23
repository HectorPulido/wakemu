"""Native request grammar and exact original fBU/fCAt publication bytes."""
import struct
import unittest

from wakfu_server import ranch_reward_retrieval as rewards


class RanchRewardWireTests(unittest.TestCase):
    def test_native_filter_and_explicit_recipient_grammar(self):
        self.assertEqual((None, 11), rewards.decode_all(struct.pack(">Bq", 0, 11)))
        self.assertEqual((22, 11), rewards.decode_all(struct.pack(">Bqq", 1, 22, 11)))
        for body in (
            b"",
            b"\x02" + b"\0" * 8,
            struct.pack(">Bq", 0, -1),
            struct.pack(">Bqq", 1, 0, 11),
            struct.pack(">Bq", 0, 11) + b"\0",
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                rewards.decode_all(body)

    def test_native_drag_has_whole_reward_ids_and_destination(self):
        self.assertEqual(
            ((41, 42), 99, 3),
            rewards.decode_selected(struct.pack(">hqqqh", 2, 41, 42, 99, 3)),
        )
        for body in (
            struct.pack(">hqh", 0, 99, 3),
            struct.pack(">hqqqh", 2, 41, 41, 99, 3),
            struct.pack(">hqqh", 1, 41, 0, 3),
            struct.pack(">hqqh", 1, 41, 99, -1),
            struct.pack(">hqqh", 2, 41, 99, 3),
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                rewards.decode_selected(body)

    def test_original_fbu_and_cat_decoder_bytes_are_exact(self):
        # Golden payloads were emitted and decoded by the original JVM probe;
        # keep these bytes local so the regression test has no .runtime dependency.
        native = {
            "pending": "0000000000000029000007e500020000000000000039000000000012d68700",
            "retrieved": "0000000000000029000007e500020000000000000039000000000012d68701",
            "cAt13964": "00000000000005a000010000000000000029000007e500020000000000000039000000000012d68701",
        }
        row = dict(
            uid=41,
            reference=2021,
            quantity=2,
            monster_uid=57,
            drop_date_ms=1234567,
            retrieved=False,
        )
        self.assertEqual(native["pending"], rewards.encode_reward(row).hex())
        row["retrieved"] = True
        self.assertEqual(native["retrieved"], rewards.encode_reward(row).hex())
        opcode, body = rewards.changed(1440, [row])
        self.assertEqual(13964, opcode)
        self.assertEqual(native["cAt13964"], body.hex())
        with self.assertRaises(ValueError):
            rewards.encode_reward(dict(row, quantity=32768))
        with self.assertRaises(ValueError):
            rewards.encode_reward(dict(row, retrieved=1))
