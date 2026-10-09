import unittest
from types import SimpleNamespace

from wakfu_server.combat_casting_range import effective_range, int32, resolve_range
from wakfu_server.combat_conditions import ConditionActor, ConditionContext
from wakfu_server.combat_native_spell_casting import definition


class NativeCastingRangeTests(unittest.TestCase):
    def test_native_range_formula_boundaries_and_wrapping(self):
        self.assertEqual(effective_range(1, 3, True, 2, False, False), (1, 5))
        self.assertEqual(effective_range(1, 3, True, 2, True, False), (1, 6))
        self.assertEqual(effective_range(2, 5, False, 0, False, True), (2, 1))
        self.assertEqual(int32((1 << 31) + 1), -(1 << 31) + 1)
        self.assertEqual(
            effective_range(1, 2, True, (1 << 31) - 1, True, False), (1, 1)
        )

    def test_installed_native_deck_condition_selects_range_and_live_bonuses(self):
        # 4816 has baseline range 2..4 and native IsSpellInDeck(6949) range 4..6.
        # A category range modifier and live RANGE characteristic then apply.
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    deck_spell_ids=frozenset({6949}),
                    excluded_deck_spell_ids=frozenset(),
                    is_player=True,
                    is_carried=False,
                    characteristics={"RANGE": 1},
                    fight_properties=frozenset(),
                )
            }
        )
        rule = definition(4816, 1, context, {})
        self.assertEqual((rule["minimum"], rule["maximum"]), (4, 6))
        self.assertTrue(rule["range_modifiable"])
        resolved = resolve_range(
            rule,
            SimpleNamespace(spell_range_modifiers={3: 1}),
            context,
        )
        self.assertEqual((resolved["minimum"], resolved["maximum"]), (4, 8))

    def test_range_requires_complete_live_authority(self):
        rule = dict(
            minimum=1,
            maximum=3,
            categories=(),
            range_modifiable=True,
        )
        with self.assertRaises(ValueError):
            resolve_range(rule, SimpleNamespace(spell_range_modifiers={}), None)
        context = ConditionContext(
            {"caster": ConditionActor(fight_properties=frozenset())}
        )
        with self.assertRaises(ValueError):
            resolve_range(rule, SimpleNamespace(), context)


if __name__ == "__main__":
    unittest.main()
