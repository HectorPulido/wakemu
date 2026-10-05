import unittest
from dataclasses import replace
from wakfu_server.combat_range_conditions import RangeFighter, fighters_breed_count
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class NativeBreedRangeTests(unittest.TestCase):
    def fixture(self):
        return tuple(
            RangeFighter((x, 0, 0), radius, None, play, sem, None, breed_id=breed)
            for x, radius, play, sem, breed in (
                (0, 0, True, False, 7),
                (2, 0, False, False, 7),
                (3, 1, None, False, 7),
                (1, 0, True, False, 8),
                (1, 0, True, True, 7),
            )
        )

    def test_exact_breed_counts_self_ko_and_summon_footprint_without_play_filter(self):
        self.assertEqual(
            fighters_breed_count(self.fixture(), center=(0, 0, 0), maximum=2, breed=7),
            3,
        )
        self.assertEqual(
            fighters_breed_count(self.fixture(), center=(0, 0, 99), maximum=1, breed=7),
            1,
        )
        self.assertEqual(
            fighters_breed_count(self.fixture(), center=(0, 0, 0), maximum=2, breed=8),
            1,
        )

    def test_nonpositive_radius_ignores_distance_but_not_sem_or_missing_center(self):
        for radius in (0, -1):
            self.assertEqual(
                fighters_breed_count(
                    self.fixture(), center=(0, 0, 0), maximum=radius, breed=7
                ),
                3,
            )
        self.assertEqual(
            fighters_breed_count(self.fixture(), center=None, maximum=0, breed=7), 0
        )
        row = replace(self.fixture()[0], physical_radius=None, position=None)
        self.assertEqual(
            fighters_breed_count((row,), center=(0, 0, 0), maximum=0, breed=7), 1
        )

    def test_unknown_breed_or_property_rejects_complete_count(self):
        for row in (
            replace(self.fixture()[0], breed_id=None),
            replace(self.fixture()[0], excluded_property=None),
        ):
            with self.assertRaises(ValueError):
                fighters_breed_count((row,), center=(0, 0, 0), maximum=2, breed=7)
        with self.assertRaises(ValueError):
            fighters_breed_count(None, center=(0, 0, 0), maximum=2, breed=7)

    def test_numeric_expression_arguments_route_to_explicit_callback(self):
        seen = []
        context = ConditionContext(
            {}, fighters_breed_range_query=lambda *args: (seen.append(args) or 3)
        )
        self.assertTrue(
            evaluate_condition(
                'GetFightersWithBreedInRange(1+1,"target",3+4)==3', context
            )
        )
        self.assertEqual(seen, [(2, "target", 7)])

    def test_invalid_signature_unknown_authority_or_partial_roster_does_not_default_zero(
        self,
    ):
        for expression in (
            'GetFightersWithBreedInRange(2,"caster")',
            "GetFightersWithBreedInRange(2,7,7)",
            'GetFightersWithBreedInRange(2,"caster",7)==0',
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ConditionContext({}))

        def unavailable(*args):
            raise ValueError("incomplete roster")

        with self.assertRaisesRegex(UnknownCondition, "incomplete roster"):
            evaluate_condition(
                'GetFightersWithBreedInRange(2,"caster",7)==0',
                ConditionContext({}, fighters_breed_range_query=unavailable),
            )
