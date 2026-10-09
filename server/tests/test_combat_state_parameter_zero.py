import unittest
from wakfu_server.combat_state_parameters import interpret_state_parameters


class StateZeroTests(unittest.TestCase):
    def test_zero_is_valid_and_not_rewritten_to_one(self):
        result = interpret_state_parameters([9316, 0, -1])
        self.assertEqual(result["level"], 0)

    def test_negative_mode_and_missing_reference_stay_rejected(self):
        for params in ([9316, -1, -1], [0, 0, -1]):
            with self.assertRaises(ValueError):
                interpret_state_parameters(params)

    def test_eWu_owned_spell_level_modes_preserve_native_fallback_and_scaling(self):
        baseline = interpret_state_parameters([9316, 4, -1, 7348])
        self.assertEqual(baseline["level"], 4)
        resolved = interpret_state_parameters([9316, 4, -1, 7348], owned_spell_level=7)
        self.assertEqual(resolved["level"], 7)

        # eVn.w supplies a float multiplier; eWu performs f2i then i2s.
        effect_parameters = [9316, 0, 4, 0, -1, 0, 7348, 0, 1.5, 0]
        from wakfu_server.combat_state_parameters import native_float_parameter

        factor = native_float_parameter(effect_parameters, 4, 1)
        scaled = interpret_state_parameters(
            [9316, 4, -1, 7348, 4],
            owned_spell_level=3,
            level_factor=factor,
        )
        self.assertEqual(scaled["level"], 4)  # 4.5 truncates toward zero.

        missing_spell = interpret_state_parameters([9316, 4, -1, 7348, 4])
        self.assertEqual(missing_spell["level"], 4)
