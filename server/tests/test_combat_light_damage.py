import unittest
from wakfu_server.combat_damage_healing import damage_amount, light_damage_element

CONTEXT = dict(
    critical=False,
    single_target=False,
    area=False,
    melee=True,
    berserk=False,
    front=True,
)


class LightDamageTests(unittest.TestCase):
    def test_native_enum_order_breaks_ties(self):
        self.assertEqual(light_damage_element({21: -10, 22: -10, 23: -10, 24: -10}), 2)
        self.assertEqual(light_damage_element({22: 20, 23: 20, 24: 20}), 4)
        self.assertEqual(light_damage_element({23: 20, 24: 20}), 3)
        with self.assertRaises(ValueError):
            light_damage_element({20: 500})

    def test_matching_resistance_not_lowest_target_resistance(self):
        source = {21: 100, 22: 200, 23: 0, 24: 0}
        target = {28: 0, 29: 100, 30: 0, 31: 0}
        for mask in range(4):
            expected = damage_amount(
                100,
                4,
                source,
                target,
                arithmetic_context=CONTEXT,
                coefficient_mask=mask,
                rng=lambda: 0.99,
            )
            self.assertEqual(
                damage_amount(
                    100,
                    1083,
                    source,
                    target,
                    arithmetic_context=CONTEXT,
                    coefficient_mask=mask,
                    rng=lambda: 0.99,
                ),
                expected,
            )
