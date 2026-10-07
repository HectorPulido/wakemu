import unittest

from wakfu_server.profession_wire import MAX_XP, level, snapshot


class ProfessionWireTests(unittest.TestCase):
    def test_single_profession_matches_native_craft_golden_and_preserves_components(
        self,
    ):
        configuration = bytes.fromhex("0801")
        additional = bytes.fromhex("18012001")
        opcode, body = snapshot(
            {
                72: {
                    "xp": 150,
                    "counters": [1, 2, 3, 4],
                    "actions": [100, 203],
                }
            },
            configuration=configuration,
            additional=additional,
        )
        expected = bytes.fromhex(
            "000000010000000e00000026"
            "0a1a08481216089601120808011002180320041a0208641a0308cb01"
            "120208011a0418012001"
        )
        self.assertEqual(opcode, 13873)
        self.assertEqual(body, expected)
        self.assertEqual(int.from_bytes(body[:4], "big"), 1)
        self.assertEqual(int.from_bytes(body[4:8], "big"), 14)
        payload_length = int.from_bytes(body[8:12], "big")
        self.assertEqual(payload_length, len(body) - 12)
        self.assertTrue(
            body.endswith(b"\x12\x02" + configuration + b"\x1a\x04" + additional)
        )

    def test_profession_level_curve_thresholds_and_cap(self):
        cases = {
            0: 0,
            74: 0,
            75: 1,
            299: 1,
            300: 2,
            7499: 9,
            7500: 10,
            749999: 99,
            750000: 100,
            MAX_XP - 1: 199,
            MAX_XP: 200,
        }
        for xp, expected_level in cases.items():
            with self.subTest(xp=xp):
                self.assertEqual(level(xp), expected_level)
        for profession_level in (1, 2, 10, 100, 200):
            threshold = 75 * profession_level * profession_level
            with self.subTest(threshold=threshold):
                self.assertEqual(level(threshold), profession_level)
                self.assertEqual(level(threshold - 1), profession_level - 1)

    def test_rejects_boolean_noninteger_and_out_of_range_xp(self):
        for xp in (True, False, 1.5, "75", -1, MAX_XP + 1):
            with self.subTest(xp=xp), self.assertRaises(ValueError):
                level(xp)

    def test_rejects_duplicate_actions_and_boolean_or_out_of_range_counters(self):
        base = {"xp": 150, "counters": [0, 0, 0, 0], "actions": [100]}
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            snapshot(
                {72: {**base, "actions": [100, 100]}},
                configuration=b"\x08\x00",
                additional=b"\x18\x00\x20\x00",
            )
        for counters in (
            [True, 0, 0, 0],
            [-1, 0, 0, 0],
            [2**31, 0, 0, 0],
            [0, 0, 0],
        ):
            with self.subTest(counters=counters), self.assertRaises(ValueError):
                snapshot(
                    {72: {**base, "counters": counters}},
                    configuration=b"\x08\x00",
                    additional=b"\x18\x00\x20\x00",
                )

    def test_rejects_invalid_profession_keys_and_mixed_key_types(self):
        state = {"xp": 0, "counters": [0, 0, 0, 0], "actions": []}
        invalid = (
            {0: state},
            {True: state},
            {"72": state},
            {72: state, "73": state},
        )
        for professions in invalid:
            with self.subTest(professions=professions), self.assertRaises(ValueError):
                snapshot(
                    professions,
                    configuration=b"\x08\x00",
                    additional=b"\x18\x00\x20\x00",
                )

    def test_rejects_incomplete_state_and_nonbyte_account_components(self):
        with self.assertRaises(ValueError):
            snapshot(
                {72: {"xp": 0, "counters": [0, 0, 0, 0]}},
                configuration=b"\x08\x00",
                additional=b"\x18\x00\x20\x00",
            )
        for configuration, additional in (
            (bytearray(b"\x08\x00"), b"\x18\x00\x20\x00"),
            (b"\x08\x00", None),
        ):
            with self.subTest(configuration=configuration, additional=additional):
                with self.assertRaises(ValueError):
                    snapshot(
                        {72: {"xp": 0, "counters": [0, 0, 0, 0], "actions": []}},
                        configuration=configuration,
                        additional=additional,
                    )


if __name__ == "__main__":
    unittest.main()
