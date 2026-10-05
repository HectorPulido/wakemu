import unittest
from wakfu_server.combat_element_selection import highest_mastery_element


class NativeElementSelectionTests(unittest.TestCase):
    def test_original_selector_presence_negative_ties_and_exclusions(self):
        self.assertIsNone(highest_mastery_element({90: 1000, 109: 2000}))
        self.assertEqual(highest_mastery_element({24: -100}), 4)
        self.assertEqual(highest_mastery_element({24: -100, 21: -100}), 1)
        self.assertEqual(highest_mastery_element({21: 300, 22: 300, 23: 400}), 3)
        self.assertEqual(highest_mastery_element({21: -1, 22: 0}), 2)
