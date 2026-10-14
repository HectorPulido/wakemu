"""Explicit terminal world-return recovery is independent of combat death."""
import unittest
from wakfu_server.health_policy import recover_finished_return, visible


class FinishedReturnHealthPolicyTests(unittest.TestCase):
    def test_terminal_casualty_returns_exactly_one_hp_even_with_hidden_wounds(self):
        self.assertEqual(recover_finished_return(129, 159, True), (128, False))
        damage, dead = recover_finished_return(129, 159, True)
        self.assertEqual(visible(129, damage, dead), 1)

    def test_living_survivor_keeps_actual_and_hidden_wounds(self):
        for damage in (0, 15, 159):
            self.assertEqual(
                recover_finished_return(129, damage, False), (damage, False)
            )

    def test_invalid_canonical_inputs_are_rejected(self):
        for maximum, damage, dead in ((0, 1, True), (129, -1, True), (129, 1, 1)):
            with self.assertRaises(ValueError):
                recover_finished_return(maximum, damage, dead)
