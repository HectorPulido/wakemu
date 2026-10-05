import unittest
from wakfu_server.combat_summon_conditions import SummonBreedRow, has_summon_with_breed
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)


class SummonBreedTests(unittest.TestCase):
    def test_exact_direct_owner_not_self_or_recursive_root(self):
        rows = (
            SummonBreedRow(7, 81, 7),
            SummonBreedRow(8, 81, 8),
            SummonBreedRow(9, 82, 7),
            SummonBreedRow(10, 83, 9),
        )
        self.assertFalse(has_summon_with_breed(rows, caller_id=7, breed=81))
        self.assertTrue(has_summon_with_breed(rows, caller_id=7, breed=82))
        self.assertFalse(has_summon_with_breed(rows, caller_id=7, breed=83))
        self.assertTrue(has_summon_with_breed(rows, caller_id=9, breed=83))
        self.assertFalse(has_summon_with_breed(rows, caller_id=7, breed=65536 + 82))

    def test_evaluated_long_and_missing_authority_remain_distinct(self):
        calls = []
        context = ConditionContext(
            {},
            has_summon_breed_query=lambda breed: (calls.append(breed) or breed == 82),
        )
        self.assertTrue(evaluate_condition("HasSummonWithBreed(80+2)", context))
        self.assertEqual(calls, [82])
        self.assertFalse(evaluate_condition("HasSummonWithBreed(81)", context))
        with self.assertRaisesRegex(UnknownCondition, "authority"):
            evaluate_condition("HasSummonWithBreed(82)", ConditionContext({}))
        with self.assertRaisesRegex(UnknownCondition, "one long"):
            evaluate_condition('HasSummonWithBreed(82,"caster")', context)

    def test_complete_empty_roster_false_and_unknown_ownership_rejects(self):
        self.assertFalse(has_summon_with_breed((), caller_id=7, breed=82))
        self.assertFalse(has_summon_with_breed(None, caller_id=None, breed=82))
        with self.assertRaisesRegex(ValueError, "identity"):
            has_summon_with_breed((SummonBreedRow(9, 82, None),), caller_id=7, breed=82)
