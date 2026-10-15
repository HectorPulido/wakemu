"""Native predicate regressions from eNG/eKl/eMj client bytecode."""
import unittest
from unittest.mock import patch
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)


class FastActivationCriteriaTests(unittest.TestCase):
    def setUp(self):
        self.aliases = patch(
            "wakfu_server.combat_conditions.canonical_aliases", return_value={}
        )
        self.aliases.start()
        self.addCleanup(self.aliases.stop)

    def test_companion_uses_native_kind_union_not_team_or_breed(self):
        for player, challenger, expected in [
            (False, True, True),
            (True, True, False),
            (False, False, False),
        ]:
            context = ConditionContext(
                actors={
                    "caster": ConditionActor(is_player=player, is_challenger=challenger)
                }
            )
            self.assertEqual(
                evaluate_condition('IsCompanion("caster")', context), expected
            )

    def test_fighter_identity_and_native_null(self):
        context = ConditionContext(actors={"target": ConditionActor(actor_id=987)})
        self.assertTrue(evaluate_condition('GetFighterId("target") == 987', context))
        self.assertTrue(evaluate_condition('GetFighterId("unknown") == -1', context))

    def test_specific_effect_native_selector_only_recognizes_target(self):
        context = ConditionContext(
            actors={
                "caster": ConditionActor(retained_effect_ids=frozenset({42})),
                "triggeringcaster": ConditionActor(retained_effect_ids=frozenset({43})),
                "target": ConditionActor(retained_effect_ids=frozenset({44})),
            }
        )
        self.assertTrue(
            evaluate_condition(
                'HasEffectWithSpecificId("triggeringCaster", 42)', context
            )
        )
        self.assertFalse(
            evaluate_condition(
                'HasEffectWithSpecificId("triggeringCaster", 43)', context
            )
        )
        self.assertTrue(
            evaluate_condition('HasEffectWithSpecificId("target", 44)', context)
        )

    def test_validation_parses_native_locals_without_querying_authority(self):
        context = ConditionContext(actors={})
        self.assertTrue(
            evaluate_condition(
                "value = if (HasState(1)) then (2) else (3); GetStateLevel(2) == value;",
                context,
                validate_only=True,
            )
        )
        self.assertTrue(evaluate_condition("IsEnnemy();", context, validate_only=True))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "False and UnsupportedPredicate()", context, validate_only=True
            )

    def test_minimum_level_uses_native_roster_filters_and_empty_sentinel(self):
        from wakfu_server.combat_max_level_conditions import fighters_min_level

        rows = [
            (0, True, set(), 100),
            (5, True, set(), 70),
            (1, True, set(), 5),
            (0, False, set(), 30),
            (0, True, {114}, 1),
        ]
        self.assertEqual(fighters_min_level(rows), 70)
        self.assertEqual(fighters_min_level(rows, "monster"), 5)
        self.assertEqual(fighters_min_level(rows, "player", False), 30)
        self.assertEqual(fighters_min_level([]), 32767)
        context = ConditionContext(
            actors={},
            fighters_min_level_query=lambda kind, playing: fighters_min_level(
                rows, kind, playing
            ),
        )
        self.assertTrue(
            evaluate_condition('GetFightersMinLevel("player") == 70', context)
        )

    def test_out_of_play_is_distinct_from_off_play(self):
        context = ConditionContext(
            actors={"caster": ConditionActor(is_out_of_play=True, is_off_play=False)}
        )
        self.assertTrue(
            evaluate_condition("IsOutOfPlay() and not IsOffPlay()", context)
        )

    def test_neo_server_uses_native_boolean_configuration(self):
        context = ConditionContext(
            actors={},
            boolean_system_configuration_query=lambda key: key == "server.group.isneo",
        )
        with patch(
            "wakfu_server.combat_system_conditions.system_predicate_catalog",
            return_value={
                "configurations": {
                    "server.group.isneo": {"boolean": True, "default": False}
                }
            },
        ):
            self.assertTrue(evaluate_condition("IsNeoServer()", context))

    def test_area_property_does_not_borrow_fighter_or_cell_properties(self):
        from wakfu_server.combat_area_predicates import has_effect_area_property
        from types import SimpleNamespace

        fight = SimpleNamespace()
        for kind in ("actor", "cell", "null"):
            self.assertFalse(
                has_effect_area_property(fight, property_id=8, target_kind=kind)
            )
        with patch(
            "wakfu_server.combat_area_property._target",
            return_value=(
                {
                    "native_current_area_properties": [8],
                    "native_area_property_source": "faV.rzt.eWs",
                },
                {},
            ),
        ):
            self.assertTrue(
                has_effect_area_property(
                    fight, property_id=8, target_kind="area", target_id=10
                )
            )
            self.assertFalse(
                has_effect_area_property(
                    fight, property_id=9, target_kind="area", target_id=10
                )
            )

    def test_world_property_range_preserves_all_roster_membership(self):
        from wakfu_server.combat_range_conditions import range_count, RangeFighter

        rows = (
            RangeFighter((1, 0, 0), 0, 1, False, False, True, True),
            RangeFighter((2, 0, 0), 0, 2, True, True, False),
        )
        self.assertEqual(
            range_count(
                rows,
                affiliation=1,
                center=(0, 0, 0),
                minimum=0,
                maximum=-1,
                relation="world_property",
                in_play=False,
            ),
            1,
        )
        context = ConditionContext(
            actors={},
            fighters_world_property_range_query=lambda radius, selector, prop: 3
            if (radius, selector, prop) == (-1, "caster", 43)
            else 0,
        )
        self.assertTrue(
            evaluate_condition(
                'GetFightersWithWorldPropertyInRange(-1, "caster", 43) == 3', context
            )
        )
