"""Native raw-profile duplicates must not become duplicate eHN map keys."""
import unittest
from wakfu_server.combat_summon_property_descriptor import descriptor_property_keys


class SummonPropertyDescriptorTests(unittest.TestCase):
    def test_actual_2450_constructor_properties_have_one94_entry(self):
        native_profile_properties = [28, 51, 15, 94, 94]
        # This is the existing NativeSummonBuilder's exact constructor boundary.
        increments = frozenset(native_profile_properties)
        self.assertEqual(descriptor_property_keys(increments), (15, 28, 51, 94))
        self.assertEqual(descriptor_property_keys(frozenset()), ())

    def test_raw_arrays_and_invalid_constructed_keys_remain_rejected(self):
        for invalid in (
            [28, 94, 94],
            (28, 94),
            frozenset({True}),
            frozenset({-1}),
            frozenset({128}),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                descriptor_property_keys(invalid)
