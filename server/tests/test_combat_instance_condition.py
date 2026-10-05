import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class InstanceConditionTests(unittest.TestCase):
    def test_native_long_property_and_caster_precedence(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(native_instance_id=1385),
                "target": ConditionActor(native_instance_id=527),
            }
        )
        self.assertTrue(evaluate_condition("GetInstanceId()==1385", context))

    def test_target_fallback_only_when_caster_absent(self):
        self.assertTrue(
            evaluate_condition(
                "GetInstanceId()==527",
                ConditionContext({"target": ConditionActor(native_instance_id=527)}),
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetInstanceId()==527",
                ConditionContext(
                    {
                        "caster": ConditionActor(),
                        "target": ConditionActor(native_instance_id=527),
                    }
                ),
            )

    def test_unknown_and_wrong_arity_reject(self):
        for expression in ("GetInstanceId()==0", 'GetInstanceId("target")==0'):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ConditionContext({}))
