"""Selected native null is distinct from an unavailable recipient snapshot."""
import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class NullPvConditionTests(unittest.TestCase):
    def test_proven_null_typed_predicates_are_false(self):
        context = ConditionContext({}, null_actor_aliases=frozenset({"target"}))
        for name in ("IsCarried", "IsCarrying", "IsCharacter"):
            with self.subTest(name=name):
                self.assertFalse(evaluate_condition(f'{name}("target")', context))
                self.assertTrue(evaluate_condition(f'not {name}("target")', context))

    def test_missing_alias_stays_unknown(self):
        for name in ("IsCarried", "IsCarrying", "IsCharacter", "HasState"):
            criteria = (
                f'{name}("target")' if name != "HasState" else 'HasState(1,"target")'
            )
            with self.subTest(name=name), self.assertRaises(UnknownCondition):
                evaluate_condition(criteria, ConditionContext({}))

    def test_state_null_requires_context_fallback_proof(self):
        for name in ("HasState", "HasStateFromLevel", "HasStateFromUser"):
            criteria = f'{name}(1,"target")'
            context = ConditionContext({}, null_actor_aliases=frozenset({"target"}))
            with self.subTest(name=name):
                with self.assertRaises(UnknownCondition):
                    evaluate_condition(criteria, context)
                self.assertFalse(
                    evaluate_condition(
                        criteria,
                        ConditionContext(
                            {},
                            null_actor_aliases=frozenset({"target"}),
                            state_null_fallback_absent=True,
                        ),
                    )
                )

    def test_non_null_fighter_missing_carry_fact_stays_unknown(self):
        context = ConditionContext({"target": ConditionActor(is_native_fighter=True)})
        for name in ("IsCarried", "IsCarrying"):
            with self.subTest(name=name), self.assertRaises(UnknownCondition):
                evaluate_condition(f'{name}("target")', context)

    def test_non_null_target_with_invalid_uid_stays_unknown(self):
        for actor_id in (None, True, 1 << 63, -(1 << 63) - 1):
            context = ConditionContext({"target": ConditionActor(actor_id=actor_id)})
            with self.subTest(actor_id=actor_id), self.assertRaises(UnknownCondition):
                evaluate_condition("GetEffectTarget()", context)

    def test_registered_nonfighter_is_not_a_carry_actor(self):
        context = ConditionContext(
            {"target": ConditionActor(is_native_fighter=False, is_carried=False)}
        )
        self.assertFalse(evaluate_condition('IsCarried("target")', context))
        self.assertFalse(evaluate_condition('IsCarrying("target")', context))

    def test_actual_fighter_carry_fact_is_preserved(self):
        context = ConditionContext(
            {
                "target": ConditionActor(
                    is_native_fighter=True,
                    is_carried=True,
                    is_carrying=True,
                )
            }
        )
        self.assertTrue(evaluate_condition('IsCarried("target")', context))
        self.assertTrue(evaluate_condition('IsCarrying("target")', context))
