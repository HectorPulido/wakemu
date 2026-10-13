"""eJS sentinel, type/team filtering and real condition callback boundary."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_nearest_ally_beacon import nearest_ally_beacon_distance
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class NearestAllyBeaconTests(unittest.TestCase):
    def query(self, fight=None, **changes):
        values = dict(caster_affiliation=0, target_position=(2, 3, 19))
        values.update(changes)
        return nearest_ally_beacon_distance(
            SimpleNamespace(native_effect_areas={}) if fight is None else fight,
            **values,
        )

    def test_known_empty_manager_returns_native_short_maximum(self):
        self.assertEqual(self.query(), 32767)

    def test_absent_target_returns_native_negative_one_before_population(self):
        self.assertEqual(self.query(SimpleNamespace(), target_position=None), -1)

    def test_type_and_team_filter_exact_minimum_including_zero(self):
        rows = [
            dict(native_type_id=2, native_fight_affiliation=0, cell=(4, 3, 0)),
            dict(native_type_id=2, native_fight_affiliation=1, cell=(2, 3, 19)),
            dict(native_type_id=0, native_fight_affiliation=0, cell=(2, 3, 19)),
        ]
        # The callback kernel receives Qq rows; actual registration verification
        # remains in _rows and is exercised by the actual native replay.
        with patch("wakfu_server.combat_effect_area_queries._rows", return_value=rows):
            self.assertEqual(self.query(), 2)
            rows.append(
                dict(native_type_id=2, native_fight_affiliation=0, cell=(2, 3, -90))
            )
            self.assertEqual(self.query(), 0)

    def test_missing_population_or_captured_team_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "population"):
            self.query(SimpleNamespace())
        with patch(
            "wakfu_server.combat_effect_area_queries._rows",
            return_value=[
                dict(native_type_id=2, cell=(1, 1, 0)),
            ],
        ):
            with self.assertRaisesRegex(ValueError, "bcM"):
                self.query()

    def test_condition_preserves_sentinels_and_invokes_real_query(self):
        context = ConditionContext({}, nearest_ally_beacon_query=self.query)
        self.assertTrue(
            evaluate_condition(
                "GetDistanceBetweenTargetAndNearestAllyBeacon() == 32767",
                context,
            )
        )
        context = ConditionContext(
            {}, nearest_ally_beacon_query=lambda: self.query(target_position=None)
        )
        self.assertTrue(
            evaluate_condition(
                "GetDistanceBetweenTargetAndNearestAllyBeacon() == -1",
                context,
            )
        )

    def test_condition_rejects_parameters_and_absent_query(self):
        for expression in (
            "GetDistanceBetweenTargetAndNearestAllyBeacon(1) == 0",
            "GetDistanceBetweenTargetAndNearestAllyBeacon() == 0",
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ConditionContext({}))


class BeaconConstructorContextTests(unittest.TestCase):
    def test_missing_native_constructor_fight_rejects_complete_negated_criterion(self):
        from wakfu_server.combat_nearest_ally_beacon import (
            require_beacon_combat_context,
        )
        from wakfu_server.combat_native_criterion_failure import (
            evaluate_native_effect_condition,
        )

        def query():
            require_beacon_combat_context(detached=True)
            return 32767

        context = ConditionContext({}, nearest_ally_beacon_query=query)
        self.assertFalse(
            evaluate_native_effect_condition(
                "not (GetDistanceBetweenTargetAndNearestAllyBeacon() < 3)",
                context,
            )
        )
        self.assertIsNone(require_beacon_combat_context(detached=False))
