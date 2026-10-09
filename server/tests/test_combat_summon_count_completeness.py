"""A complete empty native GF histogram differs from an unknown snapshot."""
import unittest

from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class SummonCountCompletenessTests(unittest.TestCase):
    def test_complete_zero_accepts_every_absent_breed_filter(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    summon_count=0,
                    summon_counts_by_breed={},
                    summon_counts_complete=True,
                )
            }
        )
        for breed in (0, 3798, 32767, 2147483647):
            self.assertTrue(
                evaluate_condition(
                    f'NbSummons("caster", {breed}) == 0',
                    context,
                )
            )

    def test_partial_and_unknown_histograms_remain_guarded(self):
        for counts, complete in (({}, False), ({3798: 1}, False), (None, True)):
            context = ConditionContext(
                {
                    "caster": ConditionActor(
                        summon_count=None,
                        summon_counts_by_breed=counts,
                        summon_counts_complete=complete,
                    )
                }
            )
            with self.assertRaises(UnknownCondition):
                evaluate_condition('NbSummons("caster", 3799) == 0', context)

    def test_complete_nonzero_snapshot_preserves_existing_breed(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    summon_count=1,
                    summon_counts_by_breed={3798: 1},
                    summon_counts_complete=True,
                )
            }
        )
        self.assertTrue(evaluate_condition('NbSummons("caster", 3798) == 1', context))
        self.assertTrue(evaluate_condition('NbSummons("caster", 3799) == 0', context))

    def test_native_wildcard_uses_total_instead_of_absent_histogram_key(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    summon_count=3,
                    summon_counts_by_breed={3798: 1, 3799: 2},
                    summon_counts_complete=True,
                )
            }
        )
        for literal in ("-1", "4294967295", "-4294967297"):
            with self.subTest(literal=literal):
                self.assertTrue(
                    evaluate_condition(
                        f'NbSummons("caster", {literal}) == 3',
                        context,
                    )
                )

    def test_signed_filter_and_long_to_int_wrapping_preserve_exact_breed(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    summon_count=2,
                    summon_counts_by_breed={3798: 2},
                    summon_counts_complete=True,
                )
            }
        )
        for literal in ("3798", "4294971094", "-4294963498"):
            with self.subTest(literal=literal):
                self.assertTrue(
                    evaluate_condition(
                        f'NbSummons("caster", {literal}) == 2',
                        context,
                    )
                )
        self.assertTrue(evaluate_condition('NbSummons("caster", -2) == 0', context))

    def test_wildcard_does_not_replace_unknown_total_with_filtered_zero(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    summon_count=None,
                    summon_counts_by_breed={},
                    summon_counts_complete=True,
                )
            }
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition('NbSummons("caster", -1) == 0', context)
        for literal in ("1.5", "True", "9223372036854775808"):
            with self.subTest(literal=literal), self.assertRaises(UnknownCondition):
                evaluate_condition(f'NbSummons("caster", {literal}) == 0', context)
