"""Selected native actor/area challenger criteria versus the full adapter."""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import Mock, patch
import unittest

import test_combat_table_condition_context as table_fixture
from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_area import NativeEffectAreaHandler
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_challenger_condition_context import challenger_table_only


class ChallengerConditionContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        table_fixture.TableConditionContextTests.setUpClass()

    def setUp(self):
        fixture = table_fixture.TableConditionContextTests()
        fixture.setUp()
        self.adapter, self.preview = fixture.adapter, fixture.preview
        authority = self.adapter.actor_authority

        def actor_kind(preview, actor):
            value = authority(preview, actor)
            return replace(
                value,
                targeting=dict(value.targeting, is_eGj=True),
                is_challenger=actor.id in (7, 8),
            )

        self.adapter.actor_authority = actor_kind
        self.preview.native_table_turn = 15
        self.preview.actors[7].position = (2, 3, 0)
        self.preview.native_effect_areas = {}
        create = NativeEffectAreaHandler(
            self.preview,
            [],
            action_id=1,
            allocate_uid=lambda: 901,
            context=lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            container=lambda invocation: (dict(container_type=None), None),
            area_affiliation=lambda *args: 0,
        )
        create.on_created = lambda row: None
        self.assertTrue(
            create(
                {"effect_class": 315},
                {"parameters": [823]},
                EffectInvocation(100, 1, 7, None, (2, 3, 0)),
            )
        )

    def context(self, criteria, invocation, *, full=False):
        if full:
            with patch(
                "wakfu_server.combat_challenger_condition_context.challenger_condition_context",
                return_value=None,
            ):
                return self.adapter.condition(
                    self.preview, {}, dict(criteria=criteria), invocation
                )
        return self.adapter.condition(
            self.preview, {}, dict(criteria=criteria), invocation
        )

    def test_original_actor_companion_and_area_kind_independent_of_team_zero_or_one(
        self,
    ):
        expressions = (
            "IsChallenger()",
            'IsChallenger("caster")',
            'IsChallenger("target")',
            "IsChallenger() and GetFightCurrentTableTurn() >= 15",
        )
        for side in (0, 1):
            self.preview.actors[7].team = self.preview.actors[8].team = side
            self.preview.actors[-7].team = 1 - side
            for source, target, expected in (
                (7, 901, False),
                (901, 7, True),
                (7, 8, True),
                (7, -7, False),
            ):
                invocation = EffectInvocation(339526, 1, source, target, (2, 3, 0))
                for criteria in expressions:
                    with self.subTest(
                        side=side, source=source, target=target, criteria=criteria
                    ):
                        fast = self.context(criteria, invocation)
                        full = self.context(criteria, invocation, full=True)
                        self.assertEqual(
                            evaluate_condition(criteria, fast),
                            evaluate_condition(criteria, full),
                        )
                        if criteria == "IsChallenger()":
                            self.assertEqual(
                                evaluate_condition(criteria, fast), expected
                            )
                        for alias in ("caster", "target"):
                            self.assertEqual(
                                fast.actors[alias].is_native_ehg,
                                full.actors[alias].is_native_ehg,
                            )
                            self.assertEqual(
                                fast.actors[alias].is_challenger,
                                full.actors[alias].is_challenger,
                            )

    def test_area_source_avoids_population_distance_ledger_and_cell_queries(self):
        from wakfu_server.combat_state_ledger import StateLedger
        from wakfu_server.combat_effect_area_targets import _rows
        from wakfu_server.combat_condition_distance import native_caster_target_distance

        invocation = EffectInvocation(339526, 1, 901, 7, (2, 3, 0))
        obstacle, rng = Mock(return_value=False), Mock(return_value=0.5)
        self.adapter.cast = replace(
            self.adapter.cast, cell_obstacle=obstacle, random_fraction=rng
        )
        criteria = "IsChallenger() and GetFightCurrentTableTurn() >= 15"
        original = StateLedger.condition_actor
        with patch.object(
            StateLedger, "condition_actor", autospec=True, side_effect=original
        ) as ledger, patch(
            "wakfu_server.combat_effect_area_targets._rows", wraps=_rows
        ) as population, patch(
            "wakfu_server.combat_condition_distance.native_caster_target_distance",
            wraps=native_caster_target_distance,
        ) as distance:
            self.assertTrue(
                evaluate_condition(criteria, self.context(criteria, invocation))
            )
            self.assertEqual(
                (
                    ledger.call_count,
                    population.call_count,
                    distance.call_count,
                    obstacle.call_count,
                    rng.call_count,
                ),
                (0, 0, 0, 0, 0),
            )
            self.assertTrue(
                evaluate_condition(
                    criteria, self.context(criteria, invocation, full=True)
                )
            )
            self.assertGreaterEqual(ledger.call_count, 1)
            self.assertGreaterEqual(population.call_count, 1)
            self.assertGreaterEqual(distance.call_count, 1)
            self.assertEqual(obstacle.call_count, 1)
            self.assertEqual(rng.call_count, 0)

    def test_invalid_selected_prototype_owner_snapshot_and_retired_pointer_keep_full_behavior(
        self,
    ):
        invocation = EffectInvocation(339526, 1, 901, 7, (2, 3, 0))
        criteria = "IsChallenger()"
        original = deepcopy(self.preview.native_effect_areas[901])
        for changes in (dict(reference=999999), dict(owner_id=999)):
            self.preview.native_effect_areas[901] = dict(deepcopy(original), **changes)
            for full in (False, True):
                with self.assertRaises((ValueError, KeyError)):
                    self.context(criteria, invocation, full=full)
        self.preview.native_effect_areas[901] = original
        self.preview.actors[7].effect_stats[92] = -1
        for full in (False, True):
            with self.assertRaisesRegex(ValueError, "absorption"):
                self.context(criteria, invocation, full=full)
        self.preview.actors[7].effect_stats[92] = 0
        from wakfu_server.combat_state_managers import removed_area_pv_scope

        row = self.preview.native_effect_areas.pop(901)
        with removed_area_pv_scope(self.preview, row):
            target = replace(invocation, caster_id=7, target_id=901)
            self.assertFalse(
                evaluate_condition(criteria, self.context(criteria, target))
            )
            self.assertFalse(
                evaluate_condition(criteria, self.context(criteria, target, full=True))
            )
        with self.assertRaises(ValueError):
            self.context(criteria, replace(invocation, caster_id=7, target_id=901))

    def test_kind_callback_mutations_unknown_kind_and_unsupported_demands_are_not_cached(
        self,
    ):
        invocation = EffectInvocation(339526, 1, 901, 7, (2, 3, 0))
        criteria = "IsChallenger() and GetFightCurrentTableTurn() >= 15"
        previous = self.adapter.actor_authority
        calls = []

        def changed(preview, actor):
            calls.append(actor.id)
            return replace(
                previous(preview, actor), is_challenger=preview.native_table_turn >= 15
            )

        self.adapter.actor_authority = changed
        for clock, expected in ((15, True), (14, False), (15, True)):
            self.preview.native_table_turn = clock
            for full in (False, True):
                self.assertEqual(
                    evaluate_condition(
                        criteria, self.context(criteria, invocation, full=full)
                    ),
                    expected,
                )
        self.assertEqual(calls, [7] * 6)
        self.adapter.actor_authority = lambda p, a: replace(
            previous(p, a), is_challenger=None
        )
        for full in (False, True):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    "IsChallenger()",
                    self.context("IsChallenger()", invocation, full=full),
                )
        for unsupported in (
            'IsChallenger("triggeringTarget")',
            'IsChallenger("castercontroller")',
            "IsChallenger() and GetTeamId() == 1",
            "IsChallenger() or UnknownNativeCall()",
            "IsChallenger() and GetRandomNumber(10) == 1",
        ):
            self.assertFalse(challenger_table_only(unsupported))
