"""Actual granted Corte distinguishes self lifesteal from the ally branch."""
import random
import struct
import unittest

import test_sacrier_threshold_pipeline as threshold_fixture
import test_sacrier_sacrifice_pipeline as ally_fixture
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
)
from wakfu_server.combat_spell_grant import granted_spells


class SacrierCortePipelineTests(unittest.TestCase):
    def test_self_corte_heals_twenty_percent_and_publishes_despite_net_recoil_loss(
        self,
    ):
        (
            character,
            monster,
            fight,
            deck,
            rng,
        ) = threshold_fixture.SacrierThresholdPipelineTests().initialized()
        self.assertIn(8586, granted_spells(fight, 7))
        actor = fight.actors[7]
        before_hp, before_wp = actor.hp, actor.effect_stats[4]
        corte = prepare_server_spell(
            struct.pack(">qqiih", 7, 8586, *actor.position),
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
        actor = corte.fight.actors[7]
        self.assertIn(
            (4805, 20), {(s.reference, s.level) for s in actor.state_ledger.entries}
        )
        self.assertLess(actor.hp, before_hp)
        self.assertEqual(actor.effect_stats[4], before_wp - 1)
        self.assertFalse(any(e["kind"] == "healing" for e in corte.fight.events))
        before_sequence = corte.fight.events[-1]["sequence"]
        hp_before_attack = actor.hp
        result = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 5032, *fight.actors[-7].position),
            character,
            {-7: monster},
            corte.fight,
            3,
            deck,
            action_id=3,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        events = [e for e in result.fight.events if e["sequence"] > before_sequence]
        hit = next(e for e in events if e["kind"] == "damage" and e["target_id"] == -7)
        heal = next(e for e in events if e["kind"] == "healing" and e["target_id"] == 7)
        recoil = sum(
            e["amount"] for e in events if e["kind"] == "damage" and e["target_id"] == 7
        )
        # This fixture has no armor, barrier, healing bonus or healing resistance.
        self.assertEqual(heal["amount"], hit["amount"] * 20 // 100)
        self.assertEqual((hit["amount"], heal["amount"], recoil), (348, 69, 854))
        self.assertEqual(
            result.fight.actors[7].hp, hp_before_attack - recoil + heal["amount"]
        )
        self.assertLess(result.fight.actors[7].hp, hp_before_attack)
        published = [
            _identity_fields(body[19:])
            for opcode, body in result.packets
            if opcode == 12613 and struct.unpack_from(">i", body, 13)[0] == 24
        ]
        self.assertEqual(
            [(p[3], p[4], p[6], p[7]) for p in published], [(416674, 69, 7, 7)]
        )

    def test_ally_corte_swaps_and_grants_damage_without_self_lifesteal(self):
        (
            characters,
            monsters,
            decks,
            fight,
        ) = ally_fixture.SacrificePipelineTests().fixture()
        rng = random.Random(7)
        for identity in (7, 8):
            fight, _ = prepare_server_initialization(
                characters[identity],
                monsters,
                fight,
                characters[identity]["account_id"],
                decks[identity],
                action_id=identity,
                rng=rng,
                fight_start=identity == 8,
                player_characters=characters,
                deck_blobs=decks,
            )
        from pathlib import Path
        import sys
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from combat_audit_turns import advance_actual_turn

        common = dict(player_characters=characters, deck_blobs=decks)
        runtime = RuntimeMessages(
            fight,
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                characters[7], monsters, p, decks[7], rng=rng, **common, **kw
            ),
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                characters[7], monsters, p, decks[7], rng=rng, **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                monsters,
                decks[7],
                action_id=action_id,
                critical=False,
                rng=rng,
                **common
            )[0],
        )
        for _ in range(4):
            if runtime.fight.current.id == 7:
                break
            advance_actual_turn(runtime)
        fight = runtime.fight
        self.assertEqual(fight.current.id, 7)
        original = {identity: fight.actors[identity].position for identity in (7, -7)}
        hp = fight.actors[7].hp
        result = prepare_server_spell(
            struct.pack(">qqiih", 7, 8586, *fight.actors[-7].position),
            characters[7],
            monsters,
            fight,
            3,
            decks[7],
            action_id=9,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
            player_characters=characters,
            deck_blobs=decks,
        )
        self.assertEqual(result.fight.actors[7].position, original[-7])
        self.assertEqual(result.fight.actors[-7].position, original[7])
        self.assertLess(result.fight.actors[7].hp, hp)
        self.assertNotIn(
            4805, {s.reference for s in result.fight.actors[7].state_ledger.entries}
        )
        self.assertIn(
            (746, 25),
            {
                (s.reference, s.level)
                for s in result.fight.actors[-7].state_ledger.entries
            },
        )
