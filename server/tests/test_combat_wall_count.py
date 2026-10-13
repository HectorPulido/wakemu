"""ePu inherits ePi's exact Qs kind/owner contract."""
import unittest
from wakfu_server.combat_wall_count import native_wall_count
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class WallCountTests(unittest.TestCase):
    def test_type_and_actual_owner_filter_without_team_inference(self):
        rows = [
            dict(native_type_id=7, owner_id=4),
            dict(native_type_id=7, owner_id=9),
            dict(native_type_id=0, owner_id=4),
            dict(native_type_id=2, owner_id=4),
        ]
        self.assertEqual(native_wall_count(rows), 2)
        self.assertEqual(native_wall_count(rows, actor_id=4, filter_owner=True), 1)
        self.assertEqual(native_wall_count(rows, actor_id=None, filter_owner=True), 0)

    def test_unknown_type_or_owner_fails_closed(self):
        for rows in ([{}], [dict(native_type_id=7)]):
            with self.assertRaises(ValueError):
                native_wall_count(rows, actor_id=4, filter_owner=True)

    def test_condition_uses_actual_query_selector_and_count(self):
        seen = []
        context = ConditionContext(
            {}, wall_count_query=lambda selector: seen.append(selector) or 2
        )
        self.assertTrue(evaluate_condition("NbWalls() == 2", context))
        self.assertTrue(evaluate_condition('NbWalls("caster") == 2', context))
        self.assertEqual(seen, [None, "caster"])

    def test_missing_query_bad_signature_and_bad_count_fail_closed(self):
        for expression, context in (
            ("NbWalls() == 0", ConditionContext({})),
            ("NbWalls(4) == 0", ConditionContext({}, wall_count_query=lambda _: 0)),
            ("NbWalls() == 0", ConditionContext({}, wall_count_query=lambda _: False)),
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, context)
