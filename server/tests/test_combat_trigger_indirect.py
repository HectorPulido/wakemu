import unittest
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.combat_trigger_identifiers import condition_identifiers


class IndirectTriggerTests(unittest.TestCase):
    def test_native_source_categories_and_force_direct_flag(self):
        for kind in (0, 1, 3, 11, 12, 25):
            for flags in (frozenset(), frozenset({34})):
                context = ConditionContext(
                    {},
                    triggering_effect_present=True,
                    triggering_container_type=kind,
                    triggering_effect_flags=flags,
                )
                self.assertEqual(
                    evaluate_condition("IsTriggeredByIndirectEffect()", context),
                    kind not in (0, 11, 12) and 34 not in flags,
                )

    def test_absent_source_is_false_unknown_is_not_assumed_false(self):
        self.assertFalse(
            evaluate_condition(
                "IsTriggeredByIndirectEffect()",
                ConditionContext({}, triggering_effect_present=False),
            )
        )
        for context in (
            ConditionContext({}),
            ConditionContext({}, triggering_effect_present=True),
            ConditionContext(
                {}, triggering_effect_present=True, triggering_effect_flags=frozenset()
            ),
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition("IsTriggeredByIndirectEffect()", context)

    def test_no_arguments_and_real_source_authority(self):
        context = ConditionContext(
            {},
            **condition_identifiers(
                {
                    "effect_flags": [],
                    "native_container": {
                        "present": True,
                        "type": 3,
                        "is_state": True,
                        "state_id": 3231,
                    },
                }
            )
        )
        self.assertTrue(evaluate_condition("IsTriggeredByIndirectEffect()", context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsTriggeredByIndirectEffect(1)", context)
