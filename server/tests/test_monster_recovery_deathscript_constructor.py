"""Actual eWE handler constructor branch, retaining exact detached guard."""
from pathlib import Path
import importlib.util
import sys
import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_summon_creation import native_fresh_summon_authority
from wakfu_server.combat_summon_initialization import detached_summon_scope
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext

import wakfu_server.combat_death_script as module


class PrivateDeathScriptConstructorTests(unittest.TestCase):
    def fixture(self):
        actor = Actor(-3, 1, (0, 0, 0), 100, 6, 3, 1, 1)
        player = Actor(7, 0, (1, 0, 0), 100, 6, 3, 1, 1)
        fight = Fight(
            77,
            [player, actor],
            {actor.position, player.position},
            {0: {player.position}, 1: {actor.position}},
        )
        del fight.actors[actor.id]
        actor.team = -1
        actor.native_controlled_by_ai = False
        authority = native_fresh_summon_authority(actor, 6)
        packets = []
        handler = module.NativeDeathScriptHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 900,
            context=lambda *args: StatExecutionContext(
                True, True, None, True, b"", None
            ),
            rng=lambda: 0,
        )
        effect = {"effect_class": 1099, "parameters": [37, 0]}
        invocation = EffectInvocation(185395, 1, actor.id, actor.id, actor.position)
        return fight, actor, authority, handler, effect, invocation, packets

    def test_source_qualified_detached_self_applies_and_removes_retained_script(self):
        fight, actor, authority, handler, effect, invocation, packets = self.fixture()
        with detached_summon_scope(fight, actor, authority):
            self.assertTrue(handler(effect, {}, invocation))
            self.assertEqual(actor.native_death_script_id, 37)
            self.assertEqual(fight.phase, "placement")
            self.assertNotIn(actor.id, fight.actors)
            self.assertEqual([row[0] for row in packets], [12613])
            module.remove_death_script(handler, 900)
            self.assertEqual(actor.native_death_script_id, -1)
            self.assertEqual(fight.owned_stat_effects, {})
            self.assertEqual([row[0] for row in packets], [12613, 13560])

    def test_lookup_or_nonself_cannot_grant_constructor_execution(self):
        fight, actor, authority, handler, effect, invocation, packets = self.fixture()
        with self.assertRaisesRegex(ValueError, "eWE fight/caster"):
            handler(effect, {}, invocation)
        with detached_summon_scope(fight, actor, authority):
            bad = EffectInvocation(185395, 1, actor.id, 7, (1, 0, 0))
            with self.assertRaisesRegex(ValueError, "eWE fight/caster"):
                handler(effect, {}, bad)
        self.assertEqual(packets, [])
        self.assertIsNone(actor.native_death_script_id)
