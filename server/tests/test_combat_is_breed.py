import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class IsBreedTests(unittest.TestCase):
    def setUp(self):
        self.context = ConditionContext(
            {
                "caster": ConditionActor(breed_id=16),
                "target": ConditionActor(breed_id=11),
            }
        )

    def test_native_names_and_default_caster(self):
        self.assertTrue(evaluate_condition('IsBreed("steamer")', self.context))
        self.assertFalse(evaluate_condition('IsBreed("unknown")', self.context))
        self.assertTrue(evaluate_condition('IsBreed("COMMON","STEAMER")', self.context))

    def test_last_selector_and_rebound_target(self):
        self.assertTrue(
            evaluate_condition('IsBreed("caster","SACRIER","target")', self.context)
        )
        self.assertFalse(
            evaluate_condition('IsBreed("target","SACRIER","caster")', self.context)
        )
        rebound = ConditionContext(
            {
                "caster": ConditionActor(breed_id=16),
                "target": ConditionActor(breed_id=16),
            }
        )
        self.assertTrue(evaluate_condition('IsBreed("target","STEAMER")', rebound))

    def test_unknown_context_and_bad_argument(self):
        for expression, context in [
            ('IsBreed("STEAMER")', ConditionContext({})),
            ("IsBreed(16)", self.context),
        ]:
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, context)
