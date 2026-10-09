import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.combat_condition_life import registered_life_predicate


class LifeConditionTests(unittest.TestCase):
    def context(self, dead=False, in_play=True):
        return ConditionContext(
            {
                "caster": ConditionActor(
                    is_native_fighter=True, is_dead=False, is_in_play=True
                ),
                "target": ConditionActor(
                    is_native_fighter=True, is_dead=dead, is_in_play=in_play
                ),
            }
        )

    def test_independent_dead_inplay_offplay_and_native_selector_defaults(self):
        for dead in (False, True):
            for in_play in (False, True):
                context = self.context(dead, in_play)
                for selector in (None, "caster", "target", "TARGET", "other"):
                    selected = selector is not None and selector.lower() == "target"
                    suffix = "()" if selector is None else f'("{selector}")'
                    self.assertEqual(
                        evaluate_condition("IsDead" + suffix, context),
                        dead if selected else False,
                    )
                    self.assertEqual(
                        evaluate_condition("IsInPlay" + suffix, context),
                        in_play if selected else True,
                    )

    def test_actual_area_ehg_and_known_null_have_separate_results(self):
        context = ConditionContext(
            {
                "target": ConditionActor(
                    is_native_fighter=False, is_native_ehg=True, is_in_play=True
                )
            }
        )
        self.assertFalse(evaluate_condition('IsDead("target")', context))
        self.assertTrue(evaluate_condition('IsInPlay("target")', context))
        null = ConditionContext({}, null_actor_aliases=frozenset(["target"]))
        self.assertFalse(evaluate_condition('IsDead("target")', null))
        self.assertFalse(evaluate_condition('IsInPlay("target")', null))

    def test_missing_dsA_does_not_infer_from_other_life_facts(self):
        actor = ConditionActor(
            is_native_fighter=True, is_in_play=False, is_off_play=True
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsDead()", ConditionContext({"caster": actor}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition('IsInPlay("target")', ConditionContext({}))

    def test_native_signatures_require_zero_or_one_literal_string(self):
        for name in ("IsDead", "IsInPlay"):
            for suffix in ("(1)", "(True)", '("caster","target")'):
                with self.subTest(name=name, suffix=suffix), self.assertRaises(
                    UnknownCondition
                ):
                    evaluate_condition(name + suffix, self.context())

    def test_actual_cell_lookup_remains_unknown_without_producer(self):
        context = replace(self.context(), target_cell_is_explicit=True)
        with self.assertRaises(UnknownCondition):
            evaluate_condition('IsInPlay("target")', context)
        resolved = replace(context, native_cell_target_fighter_resolved=True)
        self.assertTrue(evaluate_condition('IsInPlay("target")', resolved))

    def test_callback_is_typed_and_shared_for_native_cell_resolution(self):
        seen = []
        context = ConditionContext(
            {},
            life_actor_query=lambda name, selector: seen.append((name, selector))
            or True,
        )
        self.assertTrue(evaluate_condition('IsInPlay("TARGET")', context))
        self.assertEqual(seen, [("IsInPlay", "target")])
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "IsDead()", replace(context, life_actor_query=lambda *args: None)
            )

    def test_registered_fighter_reads_baF_and_explicit_dsA_only(self):
        actor = SimpleNamespace(id=7, hp=0, native_is_dead=False)
        fight = SimpleNamespace(actors={7: actor})
        authority = lambda fight, actor: SimpleNamespace(
            targeting={"is_eGj": True, "baF": True}
        )
        self.assertTrue(registered_life_predicate(fight, authority, "IsInPlay", 7))
        self.assertFalse(registered_life_predicate(fight, authority, "IsDead", 7))
        del actor.native_is_dead
        with self.assertRaises(ValueError):
            registered_life_predicate(fight, authority, "IsDead", 7)

    def test_registered_area_has_eHg_inplay_but_no_eGj_dead_predicate(self):
        fight = SimpleNamespace(actors={})
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            return_value=object(),
        ), patch(
            "wakfu_server.combat_area_authority.area_guards",
            return_value={"baF": False},
        ):
            self.assertFalse(registered_life_predicate(fight, None, "IsInPlay", 99))
            self.assertFalse(registered_life_predicate(fight, None, "IsDead", 99))


if __name__ == "__main__":
    unittest.main()
