"""eMs population filters, exact single endpoint and fcr cleanup contract."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_enemy_condition_los import enemy_condition_los
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class EnemyConditionLosTests(unittest.TestCase):
    def test_native_population_team_in_play_and_single_endpoint(self):
        selected = SimpleNamespace(id=7, native_los_height=3)
        rows = [
            SimpleNamespace(id=1, team=0),
            SimpleNamespace(id=2, team=1),
            SimpleNamespace(id=3, team=1),
        ]
        fight = SimpleNamespace(
            native_global_pv_collections={}, native_qi_visibility_ignored_slots=[9]
        )
        with patch(
            "wakfu_server.combat_native_actor_lookup.native_actor",
            return_value=selected,
        ), patch(
            "wakfu_server.combat_native_actor_lookup.native_actor_population",
            return_value=rows,
        ), patch(
            "wakfu_server.combat_global_pv_collections.global_fighter_guards",
            side_effect=lambda f, i: {"baF": i != 2},
        ), patch(
            "wakfu_server.combat_casting_los.native_casting_los", return_value=True
        ) as rays:
            self.assertTrue(
                enemy_condition_los(
                    fight,
                    lambda *_: SimpleNamespace(targeting={"is_eGj": True}),
                    affiliation=0,
                    target_id=7,
                    target_position=(8, 9, 4),
                )
            )
        self.assertEqual(rays.call_count, 1)
        self.assertEqual(rays.call_args.args[2:], (3, (8, 9, 4), selected))
        self.assertEqual(fight.native_qi_visibility_ignored_slots, [])

    def test_no_target_returns_false_and_missing_population_fails_closed(self):
        self.assertFalse(
            enemy_condition_los(
                SimpleNamespace(),
                None,
                affiliation=0,
                target_id=7,
                target_position=None,
            )
        )
        with patch(
            "wakfu_server.combat_native_actor_lookup.native_actor",
            return_value=SimpleNamespace(id=7),
        ):
            with self.assertRaisesRegex(ValueError, "population"):
                enemy_condition_los(
                    SimpleNamespace(),
                    None,
                    affiliation=0,
                    target_id=7,
                    target_position=(0, 0, 0),
                )

    def test_fcr_exception_still_clears_native_visibility_exclusions(self):
        selected = SimpleNamespace(id=7)
        fight = SimpleNamespace(
            native_global_pv_collections={}, native_qi_visibility_ignored_slots=[9]
        )
        with patch(
            "wakfu_server.combat_native_actor_lookup.native_actor",
            return_value=selected,
        ), patch(
            "wakfu_server.combat_native_actor_lookup.native_actor_population",
            return_value=[SimpleNamespace(id=3, team=1)],
        ), patch(
            "wakfu_server.combat_global_pv_collections.global_fighter_guards",
            return_value={"baF": True},
        ), patch(
            "wakfu_server.combat_casting_los.native_casting_los",
            side_effect=ValueError("actual ray missing"),
        ):
            with self.assertRaisesRegex(ValueError, "ray missing"):
                enemy_condition_los(
                    fight,
                    lambda *_: SimpleNamespace(targeting={"is_eGj": True}),
                    affiliation=0,
                    target_id=7,
                    target_position=(8, 9, 4),
                )
        self.assertEqual(fight.native_qi_visibility_ignored_slots, [])

    def test_condition_requires_typed_query_and_literal_selector(self):
        seen = []
        context = ConditionContext(
            {}, enemy_line_of_sight_query=lambda selector: seen.append(selector) or True
        )
        self.assertTrue(
            evaluate_condition('HasLineOfSightFromEnemy("caster")', context)
        )
        self.assertEqual(seen, ["caster"])
        for expression, ctx in (
            ("HasLineOfSightFromEnemy()", context),
            ("HasLineOfSightFromEnemy(1)", context),
            ('HasLineOfSightFromEnemy("caster")', ConditionContext({})),
            (
                'HasLineOfSightFromEnemy("caster")',
                ConditionContext({}, enemy_line_of_sight_query=lambda _: 1),
            ),
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ctx)
