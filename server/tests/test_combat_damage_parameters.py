import unittest
from wakfu_server.combat_damage_parameters import (
    interpret_damage_parameters,
    interpret_damage_flags,
    damage_effect_level,
    damage_mastery_context,
)
from wakfu_server.combat_damage_healing import resolve_damage


class DamageParameterTests(unittest.TestCase):
    def test_native_mastery_context_forced_range_and_actor_radius(self):
        context = dict(
            source_xy=(0, 0),
            target_xy=(4, 0),
            source_radius=1,
            target_radius=1,
            source_total_hp=499,
            source_total_max_hp=1000,
        )
        result = damage_mastery_context([], **context)
        self.assertTrue(result["melee"])
        self.assertFalse(result["ranged"])
        self.assertTrue(result["berserk"])
        result = damage_mastery_context([4, 22, 23, 24], **context)
        self.assertTrue(all(result.values()))
        self.assertFalse(
            damage_mastery_context([], **dict(context, source_total_hp=500))["berserk"]
        )

    def test_native_parameter_counts_percent_types_and_fallback(self):
        hp = dict(
            source_hp=300, source_max_hp=1000000, target_hp=600, target_max_hp=1000000
        )
        for kind, expected in enumerate((10, 100000, 30, 99970, 100000, 60, 99940)):
            result = interpret_damage_parameters(
                [10, 0, 3, 0, kind, 0], 0, hp_context=hp, rng=lambda: 0.99
            )
            self.assertEqual(result["base"], expected)
        self.assertEqual(
            interpret_damage_parameters([80, 0], 0, hp_context={}, rng=None)[
                "coefficient_mask"
            ],
            3,
        )
        self.assertEqual(
            interpret_damage_parameters([80, 0, 0, 0], 0, hp_context={}, rng=None)[
                "coefficient_mask"
            ],
            0,
        )
        self.assertEqual(
            interpret_damage_parameters(
                [80, 0, 3, 0, 99, 0], 0, hp_context={}, rng=None
            )["base"],
            80,
        )
        with self.assertRaises(ValueError):
            interpret_damage_parameters([10, 0, 3, 0, 1, 0], 0, hp_context={}, rng=None)

    def test_native_level_precedence_and_parameter_growth(self):
        self.assertEqual(
            damage_effect_level(context_override=10, container_level=20), 10
        )
        self.assertEqual(
            damage_effect_level(context_override=-1, container_level=20), 20
        )
        self.assertEqual(
            damage_effect_level(context_override=None, container_level=None), 0
        )
        self.assertEqual(
            damage_effect_level(context_override=65537, container_level=20), 1
        )
        self.assertEqual(
            interpret_damage_parameters([10, 0.5], 20, hp_context={}, rng=None)["base"],
            20,
        )

    def test_native_flags_and_explicit_unknowns(self):
        ctx = dict(container_type=11, executable=True, actors_present=True)
        self.assertFalse(interpret_damage_flags([], **ctx)["indirect"])
        self.assertTrue(
            interpret_damage_flags([], **dict(ctx, container_type=None))["indirect"]
        )
        result = interpret_damage_flags([2, 28, 34, 100], **dict(ctx, container_type=7))
        self.assertFalse(result["indirect"])
        self.assertFalse(result["block_enabled"])
        self.assertTrue(result["bypass_armor_and_barrier"])
        self.assertEqual(result["unhandled_flags"], (100,))

    def test_native_four_coefficient_mask_vectors(self):
        arithmetic = dict(
            critical=False,
            single_target=False,
            area=False,
            melee=True,
            berserk=False,
            front=True,
        )
        absorption = dict(
            source_barrier=0,
            target_armor=0,
            target_virtual_hp=0,
            target_hp=1000,
            blocked=False,
            bypass_armor_and_barrier=False,
            frozen_stats=(),
        )
        for mask, expected in enumerate((200, 800, 100, 600)):
            result = resolve_damage(
                200,
                1,
                {20: 100, 48: 100},
                {49: 50},
                arithmetic_context=arithmetic,
                absorption_context=absorption,
                coefficient_mask=mask,
                rng=lambda: 0.99,
            )
            self.assertEqual(result["hp_loss"], expected)
