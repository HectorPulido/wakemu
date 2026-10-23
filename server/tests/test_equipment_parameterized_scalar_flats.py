"""Native fixed and dynamic eWQ/eWR parameter shapes stay on flat snapshots."""

import unittest

from wakfu_server.equipment_stats import CATALOG, _flat


def _effect(reference, generic):
    matches = [
        effect
        for effect in CATALOG[reference]["effects"]
        if effect.get("generic") == generic
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"expected one native effect {generic} on item {reference}, got {len(matches)}"
        )
    return matches[0]


class ParameterizedScalarFlatTests(unittest.TestCase):
    def test_original_fixed_two_parameter_roots_resolve_native_characteristics(self):
        expected = {
            29221: {82: (28, 61), 83: (29, 61), 84: (30, 61)},
            29222: {82: (28, 61), 83: (29, 61), 84: (30, 61)},
            20951: {149: (52, 127)},
            21866: {149: (52, 155)},
        }
        for reference, by_generic in expected.items():
            for generic, flat in by_generic.items():
                with self.subTest(reference=reference, generic=generic):
                    effect = _effect(reference, generic)
                    if generic in (82, 83, 84):
                        self.assertEqual(effect["parameter_count"], 2)
                    self.assertEqual(_flat(effect), flat)

    def test_original_dynamic_three_parameter_reductions_keep_native_sign(self):
        for reference in (28320, 28321):
            with self.subTest(reference=reference):
                effect = _effect(reference, 40)
                self.assertEqual(effect["values"], [40, 0, 121])
                self.assertEqual(_flat(effect), (121, -40))

    def test_percent_chance_and_non_scalar_shapes_remain_fail_closed(self):
        fixed = _effect(20951, 149)
        self.assertIn(fixed["parameter_count"], (1, 2))
        self.assertEqual(fixed["values"], [127, 3])
        self.assertEqual(fixed["params"], [127.0, 0.0, 3.0, 0.0])
        self.assertEqual(_flat(fixed), (52, 127))
        # With native count1, eWW does not read the extra exported value.
        ignored_second = dict(fixed, values=[127, 1])
        self.assertEqual(
            _flat(ignored_second),
            (52, 127) if fixed["parameter_count"] == 1 else None,
        )
        # Count2 is the form that actually reads the second parameter. Native
        # percent mode is exactly 1 and remains outside the flat reducer.
        percent = dict(
            fixed,
            parameter_count=2,
            values=[127, 1],
            params=[127.0, 0.0, 1.0, 0.0],
        )
        self.assertIsNone(_flat(percent))
        for changed in (
            dict(fixed, effect_criteria=True),
            dict(fixed, has_triggers=True),
            dict(fixed, target_mask=1),
            dict(fixed, native_variant=1),
            dict(fixed, native_active_effect=True),
            dict(fixed, generic=150),
            dict(fixed, stat_id=53),
        ):
            with self.subTest(changed=changed):
                self.assertIsNone(_flat(changed))
