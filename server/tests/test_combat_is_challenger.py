import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class IsChallengerTests(unittest.TestCase):
    def test_default_target_and_explicit_caster_not_team(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(is_challenger=True, fight_affiliation=1),
                "target": ConditionActor(is_challenger=False, fight_affiliation=0),
            }
        )
        self.assertFalse(evaluate_condition("IsChallenger()", context))
        self.assertTrue(evaluate_condition('IsChallenger("CASTER")', context))

    def test_companion_true_is_authoritative_and_rebound_target(self):
        context = ConditionContext(
            {"target": ConditionActor(is_challenger=True, is_player=False)}
        )
        self.assertTrue(evaluate_condition("IsChallenger()", context))

    def test_unknown_kind_remains_unknown(self):
        for actors in ({}, {"target": ConditionActor(is_player=True)}):
            with self.assertRaises(UnknownCondition):
                evaluate_condition("IsChallenger()", ConditionContext(actors))
