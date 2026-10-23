import struct
import unittest

from wakfu_server.objectives.environmental_results import result_packet


class EnvironmentalResultTests(unittest.TestCase):
    def packet(self, **changes):
        values = dict(
            challenge_id=-2311,
            secondary_id=17,
            name="Héctor",
            result_parameter=6,
            rank_minus_one=0,
            result_value=230,
        )
        values.update(changes)
        return result_packet(**values)

    def test_installed_result_layout_and_utf8_byte_length(self):
        opcode, payload = self.packet()
        self.assertEqual(opcode, 13263)
        self.assertEqual(
            payload,
            struct.pack(">iib", -2311, 17, 7)
            + "Héctor".encode("utf-8")
            + struct.pack(">ihi", 6, 0, 230),
        )
        self.assertEqual(len(payload), 26)

    def test_null_names_and_signed_native_boundaries(self):
        for name in (None, ""):
            with self.subTest(name=name):
                _, payload = self.packet(
                    name=name,
                    challenge_id=-(2**31),
                    secondary_id=2**31 - 1,
                    result_parameter=-(2**31),
                    rank_minus_one=-(2**15),
                    result_value=2**31 - 1,
                )
                self.assertEqual(len(payload), 19)
                self.assertEqual(
                    struct.unpack(">iibihi", payload),
                    (-(2**31), 2**31 - 1, 0, -(2**31), -(2**15), 2**31 - 1),
                )
        self.assertEqual(len(self.packet(name="é" * 63 + "x")[1]), 146)

    def test_unsafe_lengths_and_numeric_coercion_are_rejected(self):
        invalid = [
            dict(name="é" * 64),
            dict(name=b"name"),
            dict(rank_minus_one=2**15),
            dict(rank_minus_one=-(2**15) - 1),
            dict(result_value=2**31),
            dict(result_parameter=True),
            dict(challenge_id=False),
            dict(secondary_id=1.0),
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.packet(**changes)


if __name__ == "__main__":
    unittest.main()
