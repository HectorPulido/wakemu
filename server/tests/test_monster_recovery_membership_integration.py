"""Private actual adapter condition path with exact detached-scope authority."""
from pathlib import Path
import importlib.util
import sys
from dataclasses import replace
import unittest
from unittest.mock import patch
from test_combat_runtime_adapter import ServerAdapterTests
from wakfu_server.combat_summon_initialization import detached_summon_scope
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition
from wakfu_server.combat_state_ledger import StateLedger

import wakfu_server.combat_runtime_adapter as adapter_module


class PrivateMembershipIntegrationTests(unittest.TestCase):
    def fixture(self):
        base = ServerAdapterTests()
        base.setUpClass()
        base.setUp()
        fight = base.preview
        actor = fight.actors[-7]
        actor.state_ledger = StateLedger(actor.id)
        original = base.adapter.actor_authority(fight, actor)
        authority = adapter_module.NativeActorAuthority(**vars(original))
        authority = replace(
            authority,
            native_constructor_in_fight=False,
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
        return fight, actor, authority, adapter

    def test_real_adapter_detached_constructor_projects_false_membership(self):
        fight, actor, authority, adapter = self.fixture()
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
                    EffectInvocation(1, 1, actor.id, actor.id, actor.position),
                )
                self.assertFalse(evaluate_condition('IsInFight("caster")', context))
                self.assertFalse(evaluate_condition('IsInFight("target")', context))

    def test_real_adapter_unqualified_placement_keeps_unknown(self):
        fight, actor, authority, adapter = self.fixture()
        fight.phase = "placement"
        context = adapter.condition(
            fight, {}, None, EffectInvocation(1, 1, actor.id, actor.id, actor.position)
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition('IsInFight("caster")', context)
