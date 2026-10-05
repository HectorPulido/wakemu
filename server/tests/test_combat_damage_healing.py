import unittest
from wakfu_server.combat_damage_healing import (
    consume_damage,
    healing_amount,
    consume_healing,
    resolve_damage,
    healing_resistance_after,
    resolve_healing,
)

HEAL_CONTEXT = dict(
    critical=False,
    single_target=False,
    area=False,
    melee=True,
    berserk=False,
    coefficient_mask=3,
    additional_mastery=0,
    additional_final=0,
    rng=lambda: 0.99,
)
DAMAGE_CONTEXT = dict(
    critical=False,
    single_target=False,
    area=False,
    melee=True,
    berserk=False,
    front=True,
)
ABSORPTION = dict(
    source_barrier=15,
    target_armor=20,
    target_virtual_hp=30,
    target_hp=100,
    blocked=False,
    bypass_armor_and_barrier=False,
    frozen_stats=(),
)


class CommonArithmeticTests(unittest.TestCase):
    def test_damage_auxiliary_fields_obey_native_coefficient_mask(self):
        from wakfu_server.combat_damage_healing import damage_amount

        context = dict(
            DAMAGE_CONTEXT, additional_mastery=100, additional_resistance=100
        )

        def calculate(mask, ctx):
            return damage_amount(
                100,
                2,
                {},
                {},
                arithmetic_context=ctx,
                coefficient_mask=mask,
                rng=lambda: 0.99,
            )

        self.assertEqual(calculate(0, context), 100)
        self.assertEqual(calculate(1, context), 200)
        baseline_resisted = calculate(2, context)
        self.assertLess(baseline_resisted, 100)
        self.assertEqual(
            baseline_resisted, calculate(3, dict(context, additional_mastery=0))
        )

    def test_healing_resistance_uses_actual_heal_and_explicit_guards(self):
        context = dict(
            target_max_hp=1000,
            current=90,
            enabled=True,
            frozen=False,
            minimum=0,
            maximum=1000,
        )
        self.assertEqual(healing_resistance_after(25, **context), 95)
        self.assertEqual(
            healing_resistance_after(25, **dict(context, enabled=False)), 90
        )
        self.assertEqual(healing_resistance_after(25, **dict(context, frozen=True)), 90)
        self.assertEqual(
            healing_resistance_after(100, **dict(context, maximum=100)), 100
        )
        result = resolve_healing(
            100,
            1,
            {},
            {},
            arithmetic_context=HEAL_CONTEXT,
            consumption_context=dict(
                target_hp=990,
                target_max_hp=1000,
                target_virtual_hp=0,
                target_max_virtual_hp=0,
                undead=False,
                bypass_undead=False,
                frozen_stats=(),
            ),
            resistance_context=context,
        )
        self.assertEqual((result["value"], result["target_heal_resistance"]), (10, 92))

    def test_native_absorption_order_and_source_barrier(self):
        result = consume_damage(101, **ABSORPTION)
        self.assertEqual(
            [
                result[k]
                for k in [
                    "barrier_absorbed",
                    "armor_absorbed",
                    "virtual_hp_absorbed",
                    "hp_loss",
                    "target_hp",
                ]
            ],
            [15, 20, 30, 36, 64],
        )
        result = consume_damage(11, **dict(ABSORPTION, source_barrier=100))
        self.assertEqual(result["barrier_absorbed"], 5)
        result = consume_damage(101, **dict(ABSORPTION, bypass_armor_and_barrier=True))
        self.assertEqual(result["hp_loss"], 71)
        self.assertEqual(result["virtual_hp_absorbed"], 30)
        self.assertEqual(result["target_armor"], 20)

    def test_native_block_and_actual_mitigation(self):
        result = consume_damage(101, **dict(ABSORPTION, blocked=True))
        self.assertEqual(result["value"], 81)
        result = resolve_damage(
            100,
            3,
            {},
            {30: 100},
            arithmetic_context=DAMAGE_CONTEXT,
            coefficient_mask=3,
            absorption_context=dict(
                ABSORPTION, source_barrier=0, target_armor=0, target_virtual_hp=0
            ),
            rng=lambda: 0.99,
        )
        self.assertEqual(result["hp_loss"], 81)

    def test_native_fat_proven_stat_vectors(self):
        for source in [{18: 25}, {20: 25}, {114: 25}]:
            self.assertEqual(healing_amount(80, 1, source, {}, **HEAL_CONTEXT), 100)
        self.assertEqual(healing_amount(100, 1, {}, {32: 100}, **HEAL_CONTEXT), 90)
        self.assertEqual(healing_amount(80, 2, {21: 25}, {}, **HEAL_CONTEXT), 100)
        self.assertEqual(
            healing_amount(80, 1, {52: 25}, {}, **dict(HEAL_CONTEXT, critical=True)),
            100,
        )
        self.assertEqual(
            healing_amount(
                80, 1, {20: 25}, {32: 100}, **dict(HEAL_CONTEXT, coefficient_mask=0)
            ),
            80,
        )

    def test_healing_overflow_and_undead_blocker(self):
        values = dict(
            target_hp=90,
            target_max_hp=100,
            target_virtual_hp=5,
            target_max_virtual_hp=20,
            undead=False,
            bypass_undead=False,
            frozen_stats=(),
        )
        result = consume_healing(30, **values)
        self.assertEqual(
            (result["value"], result["hp_gain"], result["virtual_hp_gain"]),
            (25, 10, 15),
        )
        with self.assertRaises(ValueError):
            consume_healing(30, **dict(values, undead=True))
        with self.assertRaises(ValueError):
            consume_damage(10, **dict(ABSORPTION, frozen_stats=None))
