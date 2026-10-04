import unittest
from wakfu_server.combat_damage_healing import resolve_damage
from wakfu_server.equipment_damage import damage


class DirectionalDamageTests(unittest.TestCase):
    def test_native_probe_back_mastery16_resistance17_and_all_masks(self):
        absorption = dict(
            source_barrier=0,
            target_armor=0,
            target_virtual_hp=0,
            target_hp=10000,
            blocked=False,
            bypass_armor_and_barrier=False,
            frozen_stats=(),
        )
        for location, expected in (
            ("FRONT", [400] * 4),
            ("SIDE", [440] * 4),
            ("BACK", [500, 1000, 405, 810]),
        ):
            for mask, amount in enumerate(expected):
                result = resolve_damage(
                    400,
                    2,
                    {16: 100},
                    {17: 100},
                    arithmetic_context=dict(
                        critical=False,
                        single_target=False,
                        area=False,
                        melee=True,
                        berserk=False,
                        front=location == "FRONT",
                        localization=location,
                    ),
                    absorption_context=absorption,
                    coefficient_mask=mask,
                    rng=lambda: 0.99,
                )
                self.assertEqual(result["value"], amount, (location, mask))

    def test_neutral_native_fSH_disables_directional_multiplier(self):
        self.assertEqual(
            damage(
                400,
                1,
                {16: 100},
                {17: 100},
                critical=False,
                single_target=False,
                area=False,
                melee=True,
                berserk=False,
                front=False,
                localization="BACK",
                rng=lambda: 0.99,
            ),
            400,
        )

    def test_nonfront_bool_without_explicit_localization_rejects(self):
        with self.assertRaisesRegex(ValueError, "explicit native localization"):
            damage(
                400,
                2,
                {},
                {},
                critical=False,
                single_target=False,
                area=False,
                melee=True,
                berserk=False,
                front=False,
            )


if __name__ == "__main__":
    unittest.main()
