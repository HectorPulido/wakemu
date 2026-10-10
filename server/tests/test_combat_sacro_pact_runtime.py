"""Pact7217 consumes actual paid WP receipt in an ordinary owned cast."""
import os
import random
import struct
import unittest
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SacroPactRuntimeTests(unittest.TestCase):
    def fixture(self):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            11,
            200,
            target_hp=2000,
            native_qi=True,
            target_distance=1,
        )
        deck, rng = encode_deck([5028], [7217]), random.Random(7)
        started, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        return character, monster, started, deck, rng

    def cast(self, fixture):
        from wakfu_server.combat_server_spell import prepare_server_spell

        character, monster, fight, deck, rng = fixture
        return prepare_server_spell(
            struct.pack(">qqiih", 7, 6065, *fight.actors[7].position),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )

    def test_paid_wp_reaches_pact_once_and_failed_reaction_rolls_back(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.fight_checkpoint_store import snapshot

        fixture = self.fixture()
        original = snapshot(fixture[2])
        actor = fixture[2].actors[7]
        resources = actor.ap, actor.mp, actor.effect_stats[4]
        seen = []
        pact_losses = []
        original_execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            if invocation.reference in (353414, 417524, 417525):
                seen.append(invocation)
            if invocation.reference == 417525:
                target = dispatcher.native_retention.fight.actors[invocation.target_id]
                before_hp = target.hp
                result = original_execute(dispatcher, invocation, **kwargs)
                pact_losses.append((before_hp, target.hp, invocation.level))
                return result
            return original_execute(dispatcher, invocation, **kwargs)

        with patch.object(EffectDispatcher, "execute", observe):
            transaction = self.cast(fixture)
        self.assertEqual(snapshot(fixture[2]), original)
        self.assertEqual(transaction.plan["costs"]["wp"], 1)
        pact = [item for item in seen if item.reference == 353414]
        self.assertEqual(len(pact), 1)
        source = pact[0].native_trigger_context
        self.assertEqual(source["cost_source"]["runner_class"], "eWf")
        self.assertEqual(
            source["cost_source"]["action_costs"], {"ap": 1, "mp": 0, "wp": 1}
        )
        self.assertEqual(source["uid"], -1)
        self.assertIn(60, source["event_ids"])
        self.assertEqual([item.reference for item in seen], [353414, 417524, 417525])
        after = transaction.fight.actors[7]
        self.assertEqual(
            (after.ap, after.mp, after.effect_stats[4]),
            (resources[0] - 1, resources[1], resources[2] - 1),
        )
        # State7903 is an immediate self-loss runner and expires during the
        # cast. Observe its real consumption before6065 heals the actor.
        total_hp = actor.hp + actor.effect_stats[92]
        total_max = actor.max_hp + actor.effect_maxima[92]
        hp_percent = (total_hp * 100) // total_max
        from wakfu_server.combat_parameters import _float32
        import math

        expected_level = math.floor(_float32(_float32(0.05) * hp_percent) + 0.5)
        self.assertEqual(len(pact_losses), 1)
        before_hp, after_hp, applied_level = pact_losses[0]
        self.assertEqual(applied_level, expected_level)
        self.assertEqual(before_hp - after_hp, actor.max_hp * expected_level // 100)
        self.assertEqual(
            next(item for item in seen if item.reference == 417524).level, 1
        )

        rng_before = fixture[4].getstate()

        def fail_reaction(dispatcher, invocation, **kwargs):
            if invocation.reference == 417525:
                raise ValueError("forced Pact child failure")
            return original_execute(dispatcher, invocation, **kwargs)

        with patch.object(EffectDispatcher, "execute", fail_reaction):
            with self.assertRaisesRegex(ValueError, "forced Pact child failure"):
                self.cast(fixture)
        self.assertEqual(snapshot(fixture[2]), original)
        self.assertEqual(fixture[4].getstate(), rng_before)
