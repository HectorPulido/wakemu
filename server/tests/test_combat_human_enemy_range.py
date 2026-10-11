"""Native eKe human enemy ranges retain eKn bounds and membership rules."""
import unittest

from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_range_conditions import RangeFighter, range_count
from wakfu_server.combat_team_count_conditions import human_actor_type


class HumanEnemyRangeTests(unittest.TestCase):
    def test_native_constructor_predicate_routes_evaluated_bounds_and_target(self):
        calls = []
        context = ConditionContext(
            {}, human_enemies_range_query=lambda *args: calls.append(args) or 1
        )
        self.assertTrue(
            evaluate_condition(
                'GetEnemiesHumanCountInRange(3,4,"target") >= 1', context
            )
        )
        self.assertEqual(calls, [(3, 4, "target", False, False)])
        self.assertTrue(
            evaluate_condition("GetEnemiesHumanCountInRange(-1)==1", context)
        )
        self.assertEqual(calls[-1], (0, -1, "caster", False, False))

    def test_missing_authority_and_malformed_signature_fail_closed(self):
        context = ConditionContext({})
        for expression in (
            "GetEnemiesHumanCountInRange(3)>0",
            "GetEnemiesHumanCountInRange(1,3,7)>0",
            "GetEnemiesHumanCountInRange()>0",
        ):
            with self.subTest(expression=expression), self.assertRaises(
                UnknownCondition
            ):
                evaluate_condition(expression, context)

    def test_enemy_human_population_preserves_native_exclusions(self):
        # Native0/5 are humans; NPC1 and summon2 cannot contribute. Property114
        # excludes allied eKz candidates, but does not exclude enemy eKe humans.
        population = [
            (0, RangeFighter((3, 0, 0), 0, 1, True, False, False)),
            (5, RangeFighter((4, 0, 0), 0, 1, True, False, False, True)),
            (0, RangeFighter((3, 0, 0), 0, 0, True, False, False)),
            (0, RangeFighter((3, 0, 0), 0, 1, False, False, False)),
            (0, RangeFighter((3, 0, 0), 0, 1, True, True, False)),
            (5, RangeFighter((3, 0, 0), 0, 1, True, False, True)),
            (1, RangeFighter((3, 0, 0), 0, 1, True, False, False)),
            (2, RangeFighter((3, 0, 0), 0, 1, True, False, False)),
        ]
        rows = tuple(
            row for actor_type, row in population if human_actor_type(actor_type)
        )
        self.assertEqual(
            range_count(
                rows,
                relation="enemy",
                affiliation=0,
                center=(0, 0, 0),
                minimum=3,
                maximum=4,
                aligned=False,
                los=False,
            ),
            2,
        )
