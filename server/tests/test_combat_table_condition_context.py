"""Differential table-only contexts against the unchanged full adapter path."""
from dataclasses import replace
from unittest.mock import Mock, patch
import unittest

import test_combat_runtime_adapter as adapter_fixture
from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_table_condition_context import table_clock_only


class TableConditionContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        adapter_fixture.ServerAdapterTests.setUpClass()

    def setUp(self):
        self.fixture = adapter_fixture.ServerAdapterTests()
        self.fixture.setUp()
        self.adapter, self.preview = self.fixture.adapter, self.fixture.preview
        self.invocation = EffectInvocation(339526, 1, 7, -7, (1, 0, 0))

    def context(self, criteria, *, full=False):
        if full:
            with patch(
                "wakfu_server.combat_table_condition_context.table_only_condition_context",
                return_value=None,
            ):
                return self.adapter.condition(
                    self.preview, {}, dict(criteria=criteria), self.invocation
                )
        return self.adapter.condition(
            self.preview, {}, dict(criteria=criteria), self.invocation
        )

    def test_differential_native_short_clock_and_actual_expressions(self):
        expressions = (
            "GetFightCurrentTableTurn() >= 6",
            "(GetFightCurrentTableTurn() % 5) == 0 and GetFightCurrentTableTurn() <> 20",
        )
        for clock in (0, 1, 5, 6, 20, 21, 32767, None, True, 32768):
            for criteria in expressions:
                with self.subTest(clock=clock, criteria=criteria):
                    self.preview.native_table_turn = clock
                    fast, full = self.context(criteria), self.context(
                        criteria, full=True
                    )
                    if type(clock) is not int or not -32768 <= clock < 32768:
                        for context in (fast, full):
                            with self.assertRaises(UnknownCondition):
                                evaluate_condition(criteria, context)
                    else:
                        self.assertEqual(
                            evaluate_condition(criteria, fast),
                            evaluate_condition(criteria, full),
                        )

    def test_unused_ledger_spatial_and_rng_work_is_removed_not_cached(self):
        from wakfu_server.combat_state_ledger import StateLedger
        from wakfu_server.combat_condition_distance import native_caster_target_distance
        from wakfu_server.combat_effect_area_targets import _rows

        criteria = "GetFightCurrentTableTurn() >= 6"
        self.preview.native_table_turn = 6
        obstacle, random = Mock(return_value=False), Mock(return_value=0.5)
        self.adapter.cast = replace(
            self.adapter.cast, cell_obstacle=obstacle, random_fraction=random
        )
        original = StateLedger.condition_actor
        with patch.object(
            StateLedger, "condition_actor", autospec=True, side_effect=original
        ) as ledger, patch(
            "wakfu_server.combat_condition_distance.native_caster_target_distance",
            wraps=native_caster_target_distance,
        ) as distance, patch(
            "wakfu_server.combat_effect_area_targets._rows", wraps=_rows
        ) as areas:
            self.assertTrue(evaluate_condition(criteria, self.context(criteria)))
            self.assertEqual(
                (
                    ledger.call_count,
                    distance.call_count,
                    areas.call_count,
                    obstacle.call_count,
                    random.call_count,
                ),
                (0, 0, 0, 0, 0),
            )
            self.assertTrue(
                evaluate_condition(criteria, self.context(criteria, full=True))
            )
            self.assertGreaterEqual(ledger.call_count, 2)
            self.assertGreaterEqual(distance.call_count, 1)
            self.assertGreaterEqual(areas.call_count, 1)
            self.assertEqual(obstacle.call_count, 1)
            self.assertEqual(random.call_count, 0)

    def test_authority_callbacks_and_new_clock_are_read_for_each_evaluation(self):
        criteria = "GetFightCurrentTableTurn() == 3"
        authority = self.adapter.actor_authority
        calls = []

        def changed(preview, actor):
            calls.append(actor.id)
            preview.native_table_turn += 1
            return authority(preview, actor)

        self.adapter.actor_authority = changed
        for full in (False, True):
            self.preview.native_table_turn = 1
            calls.clear()
            self.assertTrue(
                evaluate_condition(criteria, self.context(criteria, full=full))
            )
            self.assertEqual(calls, [7, -7])
        self.adapter.actor_authority = authority
        self.preview.native_table_turn = 8
        self.assertTrue(
            evaluate_condition(
                "GetFightCurrentTableTurn() == 8",
                self.context("GetFightCurrentTableTurn() == 8"),
            )
        )
        invocation = self.invocation
        for bad in (
            replace(invocation, caster_id=999),
            replace(invocation, target_id=999),
        ):
            self.invocation = bad
            for full in (False, True):
                with self.assertRaisesRegex(ValueError, "Unregistered non-null"):
                    self.context(criteria, full=full)
        self.invocation = invocation
        self.preview.actors[-7].effect_stats[92] = -1
        for full in (False, True):
            with self.assertRaisesRegex(ValueError, "absorption"):
                self.context(criteria, full=full)

    def test_mixed_rng_and_unsupported_branches_keep_original_full_validation(self):
        for criteria in (
            "GetTeamId() == 1",
            "False and UnknownNativeCall()",
            "GetFightCurrentTableTurn(1) == 1",
            "GetFightCurrentTableTurn() > variable",
        ):
            self.assertFalse(table_clock_only(criteria))
        criteria = "GetFightCurrentTableTurn() >= 1 and GetRandomNumber(10) == 7"
        self.assertFalse(table_clock_only(criteria))
        self.preview.native_table_turn = 1
        random = Mock(return_value=7)
        self.adapter.cast = replace(self.adapter.cast, random_number=random)
        for full in (False, True):
            self.assertTrue(
                evaluate_condition(criteria, self.context(criteria, full=full))
            )
        self.assertEqual(random.call_count, 2)
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetFightCurrentTableTurn() > 0 or UnknownNativeCall()",
                self.context("GetFightCurrentTableTurn() > 0 or UnknownNativeCall()"),
            )
