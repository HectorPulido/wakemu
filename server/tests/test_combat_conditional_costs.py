import unittest
from wakfu_server.combat_conditional_costs import (
    resolve_costs,
    catalog,
    native_catalog,
    native_modifiers,
)
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
)


class ConditionalCostTests(unittest.TestCase):
    def test_all_spell_categories_and_absent_metadata_is_not_empty(self):
        self.assertEqual(len(native_catalog()["spell_categories"]), 722)
        with self.assertRaises(UnknownCondition):
            native_modifiers(999999, {})
        with self.assertRaises(UnknownCondition):
            native_modifiers(6260, None)
        categories = native_catalog()["spell_categories"]["6260"]
        modifier = native_modifiers(6260, {categories[0]: -2})
        self.assertEqual(modifier, dict(ap=-2, mp=0, wp=0))

    def context(self, states=(), deck=()):
        return ConditionContext(
            {
                "caster": ConditionActor(
                    state_ids=frozenset(states),
                    deck_spell_ids=frozenset(deck),
                    excluded_deck_spell_ids=frozenset(),
                    is_player=True,
                )
            }
        )

    def test_native_iop_cost_replaces_base_on_state(self):
        base = dict(ap=4, mp=0, wp=0, conditional_rules=1)
        self.assertEqual(resolve_costs(4785, 1, base, self.context())["ap"], 4)
        self.assertEqual(resolve_costs(4785, 1, base, self.context([6117]))["ap"], 3)
        self.assertEqual(
            resolve_costs(
                4785, 200, base, self.context([6117]), modifiers=dict(ap=-5, mp=0, wp=0)
            )["ap"],
            0,
        )

    def test_unknown_context_and_ambiguous_overlap_rejected(self):
        base = dict(ap=4, mp=0, wp=0, conditional_rules=1)
        with self.assertRaises(UnknownCondition):
            resolve_costs(4785, 1, base, ConditionContext({"caster": ConditionActor()}))
        rule = lambda ap: dict(criteria="HasState(6117)", levels=[[ap, 0, 0]] * 200)
        with self.assertRaises(UnknownCondition):
            resolve_costs(1, 1, base, self.context([6117]), rules=[rule(2), rule(3)])
        self.assertEqual(
            resolve_costs(1, 1, base, self.context([6117]), rules=[rule(2), rule(2)])[
                "ap"
            ],
            2,
        )

    def test_unknown_equal_cost_is_proven_irrelevant_not_guessed(self):
        base = dict(ap=4, mp=0, wp=0, conditional_rules=1)
        rules = [dict(criteria="UnknownNativeCondition()", levels=[[4, 0, 0]] * 200)]
        result = resolve_costs(1, 1, base, self.context(), rules=rules)
        self.assertEqual((result["ap"], result["irrelevant_unknown_rules"]), (4, 1))
        rules.append(dict(criteria="HasState(6117)", levels=[[2, 0, 0]] * 200))
        with self.assertRaises(UnknownCondition):
            resolve_costs(1, 1, base, self.context([6117]), rules=rules)
        rules.pop()
        rules[0]["levels"][0] = [2, 0, 0]
        with self.assertRaises(UnknownCondition):
            resolve_costs(1, 1, base, self.context(), rules=rules)

    def test_native_deck_rule_and_catalog_coverage(self):
        spell, rules = next(
            (s, r)
            for s, r in catalog().items()
            if len(r) == 1 and r[0]["criteria"] == "IsSpellInDeck(6949)"
        )
        selected = rules[0]["levels"][0]
        base = dict(ap=9, mp=0, wp=0, conditional_rules=1)
        result = resolve_costs(int(spell), 1, base, self.context(deck=[6949]))
        self.assertEqual([result[k] for k in ("ap", "mp", "wp")], selected)
        self.assertEqual(len(catalog()), 225)
