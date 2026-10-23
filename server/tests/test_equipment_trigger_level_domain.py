"""Native 1020 child-level domains use complete signed-short witnesses."""
import unittest
from copy import deepcopy

from wakfu_server import combat_equipment_trigger_level_domain as domain
from wakfu_server.combat_equipment_dynamic_levels import UnknownDynamicLevel


def _leaf(family, parameters, count):
    return {
        "effect_class": family,
        "parameters": list(parameters),
        "parameter_count": count,
        "minimum_level": 0,
        "maximum_level": 32767,
        "children": [],
        "target_masks": [None] * 7,
        "native_execution_mode": 0,
        "native_timing_definition": {"clock_on_caster": False, "clock_on_target": True},
        "probability_per_level": 0,
    }


class EquipmentTriggerLevelDomainTests(unittest.TestCase):
    def test_native12195_and14083_children_keep_short_domain_endpoints(self):
        for group, effects, expected in (
            (
                {"children": [71131, 240961]},
                {
                    "71131": _leaf(1, [0, 1, 0, 0], 2),
                    "240961": _leaf(1, [1000, 0, 0, 0], 2),
                },
                ((71131, 0), (71131, 999), (240961, 1000), (240961, 32767)),
            ),
            (
                {"children": [64591, 64590]},
                {
                    "64591": _leaf(25, [0, 1, 2, 0], 2),
                    "64590": _leaf(430, [0, 0, -100, 0, 0, 0], 3),
                },
                ((64591, 0), (64591, 32767), (64590, 0), (64590, 32767)),
            ),
        ):
            with self.subTest(children=group["children"]):
                if group["children"] == [71131, 240961]:
                    effects["71131"]["maximum_level"] = 999
                    effects["240961"]["minimum_level"] = 1000
                self.assertEqual(
                    domain.child_domain_witnesses(group, effects), expected
                )

    def test_native13946_leaves_have_complete_short_domain_witnesses(self):
        effects = {
            "66438": _leaf(25, [0, 1, 2, 0], 2),
            "66439": _leaf(430, [0, 0, -100, 0, 0, 0], 3),
        }
        group = {"children": [66438, 66439]}
        self.assertEqual(
            domain.child_domain_witnesses(group, effects),
            ((66438, 0), (66438, 32767), (66439, 0), (66439, 32767)),
        )

    def test_only_mode_and_selector_invariants_are_admitted(self):
        valid430 = _leaf(430, [0, 0, -100, 0, 0, 0], 3)
        self.assertEqual(domain.leaf_domain_witnesses(valid430), (0, 32767))
        # For430, pair one is the dynamic amount; pair zero is its mode.
        amount_growth = deepcopy(valid430)
        amount_growth["parameters"][3] = 0.25
        self.assertEqual(domain.leaf_domain_witnesses(amount_growth), (0, 32767))
        mode_growth = deepcopy(valid430)
        mode_growth["parameters"][1] = 0.25
        with self.assertRaises(UnknownDynamicLevel):
            domain.leaf_domain_witnesses(mode_growth)

        valid_heal = _leaf(25, [0, 1, 2, 0], 2)
        self.assertEqual(domain.leaf_domain_witnesses(valid_heal), (0, 32767))
        selector_growth = deepcopy(valid_heal)
        selector_growth["parameters"][3] = 1
        with self.assertRaises(UnknownDynamicLevel):
            domain.leaf_domain_witnesses(selector_growth)

    def test_unproven_damage_probability_timing_and_nested_subscriptions_defer(self):
        damage = _leaf(1, [1000, -1, 0, 0], 2)
        with self.assertRaises(UnknownDynamicLevel):
            domain.leaf_domain_witnesses(damage)
        damage = _leaf(1, [1000, 0, 0, 0], 2)
        damage["probability_per_level"] = 0.01
        with self.assertRaises(UnknownDynamicLevel):
            domain.leaf_domain_witnesses(damage)
        damage = _leaf(1, [1000, 0, 0, 0], 2)
        damage["native_execution_mode"] = 2
        damage["native_definition_class"] = "eVy"
        damage["native_timing_definition"]["ryE"] = 0
        damage["native_timing_definition"]["ryF"] = 1
        with self.assertRaises(UnknownDynamicLevel):
            domain.leaf_domain_witnesses(damage)
        nested = _leaf(430, [0, 0, -100, 0, 0, 0], 3)
        nested["target_masks"][1] = [2]
        with self.assertRaises(UnknownDynamicLevel):
            domain.leaf_domain_witnesses(nested)


if __name__ == "__main__":
    unittest.main()
