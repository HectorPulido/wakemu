import unittest

from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class FightModelConditionTests(unittest.TestCase):
    def test_uses_authoritative_signed_byte_model_in_numeric_expressions(self):
        context = ConditionContext({}, fight_model_query=lambda: -114)
        self.assertTrue(evaluate_condition("GetFightModel() == -114", context))
        self.assertTrue(evaluate_condition("GetFightModel() + 114 == 0", context))
        self.assertFalse(evaluate_condition("GetFightModel() == 2", context))

    def test_native_unresolved_fight_is_distinct_from_missing_authority(self):
        self.assertTrue(
            evaluate_condition(
                "GetFightModel() == 0",
                ConditionContext({}, fight_model_query=lambda: 0),
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetFightModel() == 0", ConditionContext({}))

    def test_requires_exact_no_argument_signature_and_authority(self):
        for expression in ("GetFightModel(2) == 2", "GetFightModel(foo=2) == 2"):
            with self.subTest(expression=expression), self.assertRaises(
                UnknownCondition
            ):
                evaluate_condition(expression, ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetFightModel() == 0", ConditionContext({}))

    def test_rejects_non_native_signed_byte_results(self):
        for value in (True, -129, 128, None):
            context = ConditionContext({}, fight_model_query=lambda value=value: value)
            with self.subTest(value=value), self.assertRaises(UnknownCondition):
                evaluate_condition("GetFightModel() == 0", context)

    def test_preserves_unknown_when_native_context_query_fails(self):
        def unavailable():
            raise ValueError("Missing actual native fight")

        with self.assertRaisesRegex(UnknownCondition, "Missing actual native fight"):
            evaluate_condition(
                "GetFightModel() == 0",
                ConditionContext({}, fight_model_query=unavailable),
            )


if __name__ == "__main__":
    unittest.main()
