import unittest
from wakfu_server.combat_property_stack import (
    add_property,
    remove_property,
    property_present,
)


class NativePropertyStackTests(unittest.TestCase):
    def test_two_effects_do_not_cancel_each_other_when_one_expires(self):
        counts = {}
        self.assertEqual(add_property(counts, 11), 1)
        self.assertEqual(add_property(counts, 11), 2)
        self.assertEqual(remove_property(counts, 11), 1)
        self.assertTrue(property_present(counts, 11))
        self.assertEqual(remove_property(counts, 11), 0)
        self.assertFalse(property_present(counts, 11))
        self.assertEqual(remove_property(counts, 11), 0)

    def test_signed_byte_overflow_matches_native_probe(self):
        counts = {11: 127}
        self.assertEqual(add_property(counts, 11), -128)
        self.assertTrue(property_present(counts, 11))
        self.assertEqual(remove_property(counts, 11), 127)
        counts[11] = -127
        self.assertEqual(remove_property(counts, 11), 0)
        self.assertNotIn(11, counts)

    def test_unknown_or_invalid_counter_is_not_an_empty_population(self):
        for counts in (None, {11: True}, {11: 128}, {128: 1}):
            with self.assertRaises(ValueError):
                add_property(counts, 11)
        with self.assertRaises(ValueError):
            add_property({}, True)
