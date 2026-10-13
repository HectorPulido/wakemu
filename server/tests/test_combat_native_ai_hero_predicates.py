"""Installed eNT/eIu contracts, including absence and typed query authority."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat.combat_native_ai_hero_predicates import (
    native_is_hero,
    registered_is_hero,
    ai_has_cast_spell,
)


class NativeAiHeroPredicateTests(unittest.TestCase):
    def test_actual_fresh_bje_constructor_publishes_account_primary_authority(self):
        from wakfu_server.combat.combat_summon_creation import (
            native_fresh_summon_authority,
        )

        actor = SimpleNamespace(
            id=-200, effective_level=1, native_controlled_by_ai=True
        )
        authority = native_fresh_summon_authority(actor, 5482)
        self.assertEqual(authority.native_account_id, 0)
        self.assertEqual(authority.native_primary_character_id, 0)
        self.assertTrue(registered_is_hero(SimpleNamespace(), actor, authority))

    def test_native_hero_oracle_rows(self):
        # Exact actual-JVM hero-oracle/result.json matrix.
        for account, actor, primary, expected in (
            (0, -200, 0, True),
            (0, -200, -200, False),
            (99, 42, 0, True),
            (99, 42, 7, True),
            (99, 42, 42, False),
            (0, 0, 0, False),
        ):
            with self.subTest(account=account, actor=actor, primary=primary):
                self.assertIs(native_is_hero(actor, account, primary), expected)

    def test_current_registry_overrides_snapshot_and_uses_native_no_entry_zero(self):
        actor = SimpleNamespace(id=-200)
        authority = SimpleNamespace(
            targeting={"is_eGj": True},
            native_account_id=0,
            native_primary_character_id=0,
        )
        fight = SimpleNamespace(native_account_primary_registry={0: -200})
        self.assertFalse(registered_is_hero(fight, actor, authority))
        fight.native_account_primary_registry.clear()
        self.assertTrue(registered_is_hero(fight, actor, authority))

    def test_missing_account_primary_or_wrong_kind_fails_closed(self):
        actor = SimpleNamespace(id=42)
        for account, primary, kind in (
            (None, 0, True),
            (99, None, True),
            (99, 42, False),
        ):
            authority = SimpleNamespace(
                targeting={"is_eGj": kind},
                native_account_id=account,
                native_primary_character_id=primary,
            )
            with self.assertRaises(ValueError):
                registered_is_hero(SimpleNamespace(), actor, authority)

    def test_hero_condition_uses_registered_query_not_player_kind(self):
        self.assertTrue(
            evaluate_condition(
                "IsHero()", ConditionContext({}, is_hero_query=lambda: True)
            )
        )
        self.assertFalse(
            evaluate_condition(
                "IsHero()", ConditionContext({}, is_hero_query=lambda: False)
            )
        )
        for expression in ('IsHero("caster")', "IsHero(1)"):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    expression, ConditionContext({}, is_hero_query=lambda: True)
                )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsHero()", ConditionContext({}))

    def test_ai_query_preserves_native_reference_and_integer_narrowing(self):
        seen = []

        def query(reference):
            seen.append(reference)
            return reference == 17

        ctx = ConditionContext({}, ai_has_cast_spell_query=query)
        self.assertTrue(evaluate_condition("AIHasCastSpell(17)", ctx))
        self.assertFalse(evaluate_condition("AIHasCastSpell(4294967295)", ctx))
        self.assertEqual(seen, [17, -1])

    def test_dynamic_ai_operand_queries_minus_one_without_evaluating_actor_context(
        self,
    ):
        seen = []
        ctx = ConditionContext(
            {}, ai_has_cast_spell_query=lambda value: seen.append(value) or False
        )
        self.assertFalse(
            evaluate_condition("AIHasCastSpell(GetCurrentFighterId())", ctx)
        )
        self.assertEqual(seen, [-1])

    def test_missing_ai_context_never_becomes_false(self):
        with self.assertRaises(ValueError):
            ai_has_cast_spell(None, 17)
        with self.assertRaises(UnknownCondition):
            evaluate_condition("AIHasCastSpell(17)", ConditionContext({}))
        with self.assertRaises(ValueError):
            ai_has_cast_spell(SimpleNamespace(has_cast_spell=lambda _: 1), 17)

    def test_explicit_ai_query_observes_actual_callback_state(self):
        recorded = set()
        ctx = SimpleNamespace(has_cast_spell=lambda spell: spell in recorded)
        self.assertFalse(ai_has_cast_spell(ctx, 17))
        recorded.add(17)
        self.assertTrue(ai_has_cast_spell(ctx, 17))
        self.assertFalse(ai_has_cast_spell(ctx, 18))


if __name__ == "__main__":
    unittest.main()
