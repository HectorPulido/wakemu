import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class ActionPresenceTests(unittest.TestCase):
    def test_family_distinct_from_reference_and_numeric_long_narrowing(self):
        actor = ConditionActor(
            retained_action_ids=frozenset({20}),
            retained_effect_ids=frozenset({197707}),
            is_native_fighter=True,
        )
        context = ConditionContext({"caster": actor})
        self.assertTrue(
            evaluate_condition('HasEffectWithActionId("caster",10+10)', context)
        )
        self.assertTrue(
            evaluate_condition('HasEffectWithActionId("caster",4294967316)', context)
        )
        self.assertFalse(
            evaluate_condition('HasEffectWithActionId("caster",197707)', context)
        )

    def test_empty_and_unknown_populations(self):
        self.assertFalse(
            evaluate_condition(
                'HasEffectWithActionId("caster",20)',
                ConditionContext(
                    {"caster": ConditionActor(retained_action_ids=frozenset())}
                ),
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'HasEffectWithActionId("caster",20)',
                ConditionContext({"caster": ConditionActor()}),
            )

    def test_actor_rebinding_and_known_null(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(retained_action_ids=frozenset({20})),
                "target": ConditionActor(retained_action_ids=frozenset({877})),
            }
        )
        self.assertTrue(
            evaluate_condition('HasEffectWithActionId("target",877)', context)
        )
        self.assertFalse(
            evaluate_condition('HasEffectWithActionId("target",20)', context)
        )
        self.assertFalse(
            evaluate_condition(
                'HasEffectWithActionId("target",20)',
                ConditionContext({}, effect_target_absent=True),
            )
        )
