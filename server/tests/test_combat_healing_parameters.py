import unittest
from wakfu_server.combat_healing_parameters import (
    interpret_healing_parameters,
    interpret_healing_flags,
    healing_mastery_context,
)
from wakfu_server.combat_damage_healing import healing_amount


class NativeHealingParametersTests(unittest.TestCase):
    def test_defaults_percent_and_byte_fallback(self):
        context = dict(
            source_hp=300, source_max_hp=1000, target_hp=600, target_max_hp=2000
        )
        for mode, expected in [
            (0, 10),
            (1, 100),
            (2, 30),
            (3, 70),
            (4, 200),
            (5, 60),
            (6, 140),
            (99, 10),
            (257, 100),
        ]:
            result = interpret_healing_parameters(
                [10, 0, 3, 0, mode, 0], 1, hp_context=context, rng=lambda: 0.99
            )
            self.assertEqual(result["base"], expected)
        self.assertEqual(
            interpret_healing_parameters([80, 0], 1, hp_context={}, rng=lambda: 0.99)[
                "coefficient_mask"
            ],
            3,
        )
        self.assertEqual(
            interpret_healing_parameters(
                [0, 0, 3, 0, 1, 0], 1, hp_context=context, rng=lambda: 0.99
            )["base"],
            0,
        )

    def test_undead_explicit_native_flags(self):
        ctx = dict(
            critical_variant=True,
            source_present=True,
            target_present=True,
            target_has_hp=True,
            undead=True,
            native_fKK=True,
            native_aZB=False,
        )
        self.assertEqual(
            interpret_healing_flags([], **ctx)["undead_damage_effect_id"], -3
        )
        self.assertFalse(interpret_healing_flags([33], **ctx)["converts_to_damage"])
        self.assertFalse(
            interpret_healing_flags([], **dict(ctx, source_present=False))["executable"]
        )

    def test_both_range_masteries_and_additional_final(self):
        context = healing_mastery_context(
            [23, 24],
            source_xy=(0, 0),
            target_xy=(1, 0),
            source_radius=0,
            target_radius=0,
            source_total_hp=100,
            source_total_max_hp=100,
        )
        self.assertTrue(context["melee"] and context["ranged"])
        kwargs = dict(
            context,
            critical=False,
            coefficient_mask=3,
            additional_mastery=0,
            additional_final=25,
            rng=lambda: 0.99,
        )
        self.assertEqual(healing_amount(80, 1, {103: 25, 104: 25}, {}, **kwargs), 150)
        self.assertEqual(
            healing_amount(
                80, 1, {103: 25, 104: 25}, {}, **dict(kwargs, coefficient_mask=0)
            ),
            80,
        )
