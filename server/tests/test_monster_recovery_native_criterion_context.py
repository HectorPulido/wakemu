"""Exact eKn no-combat failure rejects whole eZR criterion, never unknowns."""
from pathlib import Path
import importlib.util
import sys
from dataclasses import replace
import unittest
from unittest.mock import patch
from test_combat_runtime_adapter import ServerAdapterTests
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.combat_summon_initialization import detached_summon_scope
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_conditions import ConditionContext, UnknownCondition

import wakfu_server.combat_native_criterion_failure as failure
import wakfu_server.combat_runtime_adapter as adapter_module


class PrivateNativeCriterionContextTests(unittest.TestCase):
    def test_actual_adapter_detached_range_query_throws_native_failure_then_whole_false(
        self,
    ):
        base = ServerAdapterTests()
        base.setUpClass()
        base.setUp()
        fight = base.preview
        actor = fight.actors[-7]
        actor.state_ledger = StateLedger(actor.id)
        authority = adapter_module.NativeActorAuthority(
            **vars(base.adapter.actor_authority(fight, actor))
        )
        authority = replace(
            authority,
            native_controller_id=actor.id,
            native_in_play=False,
            targeting={
                **authority.targeting,
                "bcN": -1,
                "dpu_id": actor.id,
                "dpr_id": actor.id,
            },
        )
        adapter = adapter_module.NativeServerRuntimeAdapter(
            actor_authority=lambda *args: authority,
            cast=adapter_module.NativeCastAuthority(**vars(base.cast)),
        )
        del fight.actors[actor.id]
        actor.team = -1
        fight.phase = "placement"
        with patch(
            "wakfu_server.combat_runtime_adapter.NativeActorAuthority",
            adapter_module.NativeActorAuthority,
        ):
            with detached_summon_scope(fight, actor, authority):
                context = adapter.condition(
                    fight,
                    {},
                    None,
                    EffectInvocation(407755, 1, actor.id, actor.id, actor.position),
                )
                with self.assertRaises(failure.NativeCriterionRuntimeFailure):
                    context.state_range_query(-1, "target", 9054, -1, True, "")
                for criterion in (
                    'GetStateCountInRange(-1,"target",9054)>=1',
                    'not (GetStateCountInRange(-1,"target",9054)>=1)',
                    'GetStateCountInRange(-1,"target",9054)>=1 or 1==1',
                ):
                    self.assertFalse(
                        failure.evaluate_native_effect_condition(criterion, context)
                    )
                from wakfu_server.combat_effect_dispatch import EffectDispatcher
                from test_combat_effect_dispatch import effect

                calls = []
                dispatcher = EffectDispatcher(
                    {
                        "407755": effect(
                            400, criteria='GetStateCountInRange(-1,"target",9054)>=1'
                        )
                    },
                    {400: lambda *args: (calls.append(args) or True)},
                    resolve=lambda definition, invocation: (invocation,),
                    condition_context=lambda invocation: context,
                    probability_accepts=lambda *args: True,
                    group_cells=lambda *args: (),
                    actor_position=lambda identity: actor.position,
                )
                self.assertFalse(
                    dispatcher.execute(
                        EffectInvocation(407755, 1, actor.id, actor.id, actor.position)
                    )
                )
                self.assertEqual(calls, [])

    def test_authoritative_queries_preserve_values_and_unknown_authority_still_throws(
        self,
    ):
        context = ConditionContext({}, state_range_query=lambda *args: 3)
        self.assertTrue(
            failure.evaluate_native_effect_condition(
                'GetStateCountInRange(-1,"target",9054)>=1', context
            )
        )
        self.assertFalse(
            failure.evaluate_native_effect_condition(
                'GetStateCountInRange(-1,"target",9054)>=4', context
            )
        )

        def missing(*args):
            raise ValueError("Ordinary authority roster changed")

        context = ConditionContext({}, state_range_query=missing)
        with self.assertRaisesRegex(UnknownCondition, "roster changed"):
            failure.evaluate_native_effect_condition(
                'GetStateCountInRange(-1,"target",9054)>=1', context
            )
        with self.assertRaises(UnknownCondition):
            failure.evaluate_native_effect_condition(
                "UnknownNativePredicate()", context
            )
