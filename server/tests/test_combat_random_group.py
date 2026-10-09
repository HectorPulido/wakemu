import unittest
from wakfu_server.combat_random_group import weighted_children, random_group_mode


class NativeRandomGroupTests(unittest.TestCase):
    def check(self, rows, count, bounds, rolls, expected):
        calls = []

        def draw(bound):
            self.assertEqual(bound, bounds[len(calls)])
            value = rolls[len(calls)]
            calls.append(bound)
            return value

        self.assertEqual(weighted_children(rows, count, draw_integer=draw), expected)
        self.assertEqual(calls, bounds)

    def test_native_weighted_boundaries_and_no_replacement(self):
        self.check([(1, 10), (2, 20), (3, 30)], 2, [60, 50], [10, 0], (1, 2))
        self.check([(1, 0), (2, 20), (3, 30)], 1, [50], [0], (1,))
        self.check([(1, 0.7), (2, 1.6)], 1, [1], [0], (1,))
        self.check([(1, 10), (2, 20)], 0, [], [], ())
        self.check([(1, 10), (2, 20)], -1, [], [], ())

    def test_undefined_total_and_invalid_rng_fail(self):
        for rows, count, draw in (
            ([(1, 0)], 1, lambda n: 0),
            ([(1, 10)], 2, lambda n: 0),
            ([(1, 10)], 1, lambda n: 10),
            ([(1, 10), (1, 20)], 1, lambda n: 0),
        ):
            with self.assertRaises(ValueError):
                weighted_children(rows, count, draw_integer=draw)

    def test_empty_criteria_pool_is_not_a_successful_native_no_op(self):
        draws = []
        with self.assertRaisesRegex(ValueError, "positive remaining probability total"):
            weighted_children([], 1, draw_integer=lambda bound: draws.append(bound))
        self.assertEqual(draws, [])
        # Native eXR skips its draw loop only when the requested count is <=0.
        self.check([], 0, [], [], ())
        self.check([], -1, [], [], ())

    def test_separate_native_parameter_positions(self):
        mode = random_group_mode(
            {"effect_class": 341, "parameters": [2, 0, 0, 1, 1, 0]},
            {"parameters": [2, 1, 1]},
        )
        self.assertFalse(mode.on_target)  # So(1) raw zero, not evaluated value1.
        self.assertTrue(mode.transmit_target)
        self.assertEqual(mode.limit, 0)  # Count governs lottery, not PT successes.

    def test_eXR_owner_raw_parameter_is_distinct_from_transmitted_target(self):
        for raw_owner, expected_target in ((0, False), (1, True), (3, False)):
            with self.subTest(raw_owner=raw_owner):
                mode = random_group_mode(
                    {"effect_class": 341, "parameters": [2, raw_owner, 0]},
                    {"parameters": [2, 1, 1]},
                )
                self.assertEqual(mode.on_target, expected_target)
                self.assertTrue(mode.transmit_target)

        # With only two defined/evaluated parameters eXR has no rFn target
        # argument; raw So(1) still controls actor-vs-cell owner routing.
        mode = random_group_mode(
            {"effect_class": 341, "parameters": [2, 1]},
            {"parameters": [2, 1]},
        )
        self.assertTrue(mode.on_target)
        self.assertTrue(mode.transmit_target)

        mode = random_group_mode(
            {"effect_class": 341, "parameters": [2, 0, 0]},
            {"parameters": [2, 1, 0]},
        )
        self.assertFalse(mode.on_target)
        self.assertFalse(mode.transmit_target)

    def test_probability_context_updates_fields_without_duplicate_identity(self):
        from wakfu_server.combat_random_group import probability_bypass_context
        from wakfu_server.combat_effects import _integer
        from wakfu_server.combat_effect_removal import _identity_fields

        original = _integer(1, 0) + _integer(2, 1) + _integer(4, -1) + _integer(7, 1)
        result = probability_bypass_context(original)
        fields = _identity_fields(result, integer_fields=(1, 2, 4, 7))
        self.assertEqual((fields[1], fields[2], fields[7]), (1, 0, 1))
        self.assertEqual(fields[4], (1 << 64) - 1)
        self.assertEqual(probability_bypass_context(result), result)
