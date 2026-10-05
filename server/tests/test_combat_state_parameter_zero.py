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
