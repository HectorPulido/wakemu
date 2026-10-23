"""Real damage-handler/staging contracts for observed Rushu score feedback.

The native constructor receipt is a bounded fixture here; the retained native
scene has separate acceptance. No native spell tree or full encounter is loaded.
"""
from copy import deepcopy
from itertools import count
import unittest

from wakfu_server.combat_boss_outgoing_policy import outgoing_score_final
from wakfu_server.combat_boss_score_policy import NOX_SCORE, RUSHU_SCORE
from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.maps.boss_score_runtime import staged_score


class BossOutgoingScoreTests(unittest.TestCase):
    def setUp(self):
        player = Actor(7, 0, (0, 0, 0), 3000000, 6, 3, 10, 1, 3, True)
        boss = Actor(-7, 1, (1, 0, 0), 3000000, 6, 3, 5, 1)
        self.fight = Fight(
            77,
            [player, boss],
            {player.position, boss.position},
            {0: {player.position}, 1: {boss.position}},
        )
        self.fight.ready(3)
        for actor in (player, boss):
            actor.effect_stats = {92: 0, 97: 0, 100: 0}
            actor.effect_maxima = {92: 0}
            actor.effect_frozen = frozenset()
            actor.physical_radius = 0
        self.fight.boss_score_profile = dict(
            policy="wakemu-boss-validated-damage-v1",
            encounter_controller=RUSHU_SCORE.name,
            minimum_score=3000000,
            bosses={"-7": dict(reference=5306, round_limit=20)},
            player_ids=[7],
            player_team=0,
            round_limit=20,
        )
        self.fight.boss_score_events = {}
        self.fight.native_timeline_round = 1
        self.fight.native_npc_initialization_receipts = {
            -7: dict(ref=5306, initialized=True, resolved_states=[dict(state_id=7000)])
        }
        self.fight.actors[7].effective_level = 200
        from wakfu_server.combat_boss_party_level_policy import freeze_level_profile

        self.fight.boss_score_profile.update(
            freeze_level_profile(self.fight.boss_score_profile, self.fight.actors)
        )
        self.uid = count(90)
        self.packets = []
        self.effect = dict(
            effect_class=1,
            parameters=[100, 0],
            native_effect_flags=[],
            native_localization_enabled=True,
        )

    def handler(self, fight=None):
        return NativeDamageHandler(
            self.fight if fight is None else fight,
            self.packets,
            action_id=1,
            allocate_uid=lambda: next(self.uid),
            rng=lambda: 0.99,
            context=lambda *args: DamageExecutionContext(
                False, True, False, True, 11, False
            ),
        )

    def damage_boss(self, amount, fight=None):
        fight = self.fight if fight is None else fight
        effect = dict(self.effect, parameters=[amount, 0])
        invocation = EffectInvocation(1, 1, 7, -7, (1, 0, 0))
        self.assertTrue(self.handler(fight)(effect, {}, invocation))

    def outgoing_amount(self, *, parameters=None, additional_final=0):
        effect = dict(self.effect, parameters=parameters or self.effect["parameters"])
        invocation = EffectInvocation(1, 1, -7, 7, (0, 0, 0))
        return self.handler()._calculate(
            effect, invocation, additional_final=additional_final
        )[2]

    def test_actual_damage_receipts_cross_steps_without_accumulating_buffs(self):
        boss = self.fight.actors[-7]
        original = deepcopy(boss.effect_stats)
        self.assertEqual(self.outgoing_amount(), 100)
        for amount, score, final in (
            (49999, 49999, 0),
            (1, 50000, 1),
            (950000, 1000000, 20),
        ):
            with self.subTest(score=score):
                self.damage_boss(amount)
                self.assertEqual(staged_score(self.fight), score)
                self.assertEqual(outgoing_score_final(self.fight, boss), final)
                self.assertEqual(self.outgoing_amount(), 100 + final)
                self.assertEqual(self.outgoing_amount(), 100 + final)
                self.assertEqual(boss.effect_stats, original)
        self.assertEqual(len(self.fight.boss_score_events), 3)

    def test_existing_final_modifiers_and_native_coefficient_suppression(self):
        self.damage_boss(1000000)
        self.fight.actors[-7].effect_stats[48] = 30
        self.assertEqual(self.outgoing_amount(additional_final=10), 160)
        # Source coefficients disabled: neither ordinary final nor score leaks in.
        self.assertEqual(
            self.outgoing_amount(parameters=[100, 0, 2, 0], additional_final=10), 100
        )

    def test_actual_source_and_constructor_required_only_for_registered_score_boss(
        self,
    ):
        self.damage_boss(50000)
        boss, player = self.fight.actors[-7], self.fight.actors[7]
        self.assertEqual(outgoing_score_final(self.fight, player), 0)
        with self.assertRaisesRegex(ValueError, "actual native constructor"):
            outgoing_score_final(self.fight, deepcopy(boss))
        self.fight.native_npc_initialization_receipts[-7]["resolved_states"] = []
        with self.assertRaisesRegex(ValueError, "actual native constructor"):
            outgoing_score_final(self.fight, boss)
        profile = self.fight.boss_score_profile
        profile["encounter_controller"] = NOX_SCORE.name
        profile["bosses"]["-7"]["reference"] = NOX_SCORE.reference
        self.assertEqual(outgoing_score_final(self.fight, boss), 0)
        del self.fight.boss_score_profile
        self.assertEqual(outgoing_score_final(self.fight, boss), 0)

    def test_discarded_damage_preview_cannot_publish_score_bonus(self):
        preview = deepcopy(self.fight)
        self.damage_boss(1000000, preview)
        self.assertEqual(outgoing_score_final(preview, preview.actors[-7]), 20)
        self.assertEqual(staged_score(self.fight), 0)
        self.assertEqual(self.outgoing_amount(), 100)
        self.assertEqual(self.fight.actors[-7].hp, 3000000)
        self.assertEqual(self.fight.boss_score_events, {})

    def test_frozen_245_multiplier_is_separate_from_score_and_respects_source_mask(
        self,
    ):
        from wakfu_server.combat_boss_party_level_policy import freeze_level_profile

        self.fight.actors[7].effective_level = 245
        self.fight.boss_score_profile.update(
            freeze_level_profile(self.fight.boss_score_profile, self.fight.actors)
        )
        self.damage_boss(1000000)
        self.fight.actors[-7].effect_stats[48] = 30
        self.assertEqual(self.outgoing_amount(additional_final=10), 192)
        self.assertEqual(
            self.outgoing_amount(parameters=[100, 0, 2, 0], additional_final=10), 100
        )
        # Changes to the live level do not replace accepted encounter facts.
        self.fight.actors[7].effective_level = 200
        self.assertEqual(self.outgoing_amount(additional_final=10), 192)

    def test_small_base_mastery_and_multiplier_keep_one_final_rng_decision(self):
        from unittest.mock import Mock
        from wakfu_server.combat_boss_party_level_policy import freeze_level_profile

        self.fight.actors[7].effective_level = 245
        self.fight.boss_score_profile.update(
            freeze_level_profile(self.fight.boss_score_profile, self.fight.actors)
        )
        self.damage_boss(1000000)
        self.fight.actors[-7].effect_stats[20] = 400
        handler = self.handler()
        handler.rng = Mock(return_value=0.99)
        invocation = EffectInvocation(1, 1, -7, 7, (0, 0, 0))
        amount = handler._calculate(dict(self.effect, parameters=[2, 0]), invocation)[2]
        self.assertEqual(amount, 14)  # 2*5mastery*1.2score*1.2level=14.4, not12.
        self.assertEqual(handler.rng.call_count, 1)

    def test_new_rushu_profile_cannot_silently_omit_or_forge_frozen_level_authority(
        self,
    ):
        profile = self.fight.boss_score_profile
        profile["outgoing_level_factor_bp"] = 12000
        with self.assertRaisesRegex(ValueError, "factor changed"):
            self.outgoing_amount()
        del profile["outgoing_level_policy"]
        with self.assertRaisesRegex(ValueError, "versioned frozen"):
            self.outgoing_amount()

    def test_actual_opening_profile_installer_freezes_owned_levels_once_before_damage(
        self,
    ):
        from types import SimpleNamespace
        from wakfu_server.combat_rushu_score_policy import install_rushu_score_profile

        self.fight.actors[7].effective_level = 245
        self.fight.boss_score_profile = None
        self.fight.native_start_event_delivered = True
        events = self.fight.boss_score_events
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=self.fight))
        self.assertTrue(install_rushu_score_profile(dispatcher))
        self.assertEqual(
            self.fight.boss_score_profile["party_effective_levels"], [[7, 245]]
        )
        self.assertEqual(
            self.fight.boss_score_profile["outgoing_level_factor_bp"], 12000
        )
        self.assertIs(self.fight.boss_score_events, events)
        self.fight.actors[7].effective_level = 200
        self.assertFalse(install_rushu_score_profile(dispatcher))
        self.assertEqual(
            self.fight.boss_score_profile["outgoing_level_factor_bp"], 12000
        )


if __name__ == "__main__":
    unittest.main()
