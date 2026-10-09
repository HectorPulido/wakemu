"""Rejected fresh creation closes only its transaction-owned preparation."""
import unittest
from dataclasses import replace
from types import SimpleNamespace

from wakfu_server.combat_summon_handler import NativeSummonHandler


class SummonPreparationCleanupTests(unittest.TestCase):
    def test_dispatcher_cancels_rejected_summon_with_canonical_callback(self):
        from wakfu_server.combat_conditions import ConditionContext
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            EffectInvocation,
        )

        handler = object.__new__(NativeSummonHandler)
        other = object()
        handler.prepared_runners = {12: other}
        definition = dict(
            effect_class=307,
            parameters=[],
            parameter_count=0,
            probability_base=100,
            probability_per_level=0,
            minimum_level=1,
            maximum_level=200,
            criteria="False",
            children=[],
        )

        def prepare(effect, values, invocation):
            handler.prepared_runners[11] = object()
            return replace(invocation, native_running_uid=11)

        dispatcher = EffectDispatcher(
            {"91": definition},
            {307: handler},
            resolve=lambda effect, invocation: (invocation,),
            condition_context=lambda invocation: ConditionContext({}),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda identity: (0, 0, 0),
            prepare_effect=prepare,
        )
        self.assertFalse(
            dispatcher.execute(EffectInvocation(91, 1, 7, None, (1, 0, 0)))
        )
        self.assertEqual(handler.prepared_runners, {12: other})

    def test_rejection_discards_exact_runner_and_is_idempotent(self):
        handler = object.__new__(NativeSummonHandler)
        other = object()
        handler.prepared_runners = {11: object(), 12: other}
        invocation = SimpleNamespace(native_running_uid=11)
        handler.cancel_prepared(invocation)
        handler.cancel_prepared(invocation)
        self.assertEqual(handler.prepared_runners, {12: other})

    def test_unprepared_rejection_preserves_other_runner(self):
        handler = object.__new__(NativeSummonHandler)
        handler.prepared_runners = {12: object()}
        handler.cancel_prepared(SimpleNamespace(native_running_uid=None))
        self.assertEqual(set(handler.prepared_runners), {12})
