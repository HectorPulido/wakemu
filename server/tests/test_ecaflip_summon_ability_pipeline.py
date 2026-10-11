"""Actual Miaumiau turn and enemy resistance debuff with full roster authority."""
import os
import random
import struct
import unittest

import test_combat_aptitude_healing_runtime as allied


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipSummonAbilityPipelineTests(unittest.TestCase):
    fixture = allied.AptitudeHealingRuntimeTests.fixture
    setUpClass = allied.AptitudeHealingRuntimeTests.__dict__["setUpClass"]

    def test_miaumiau_owned_ability_debuffs_marked_enemy_near_actual_controller(self):
        from class_spell_eligible_targets import eligible_cast_targets
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
            prepare_server_turn_start,
            prepare_server_turn_end,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.fight_checkpoint_store import snapshot

        for seed in range(24):
            fight, characters, monster, decks = self.fixture(
                active_spells=(7225,),
                caster_breed=6,
                level=200,
                caster_aptitudes=(),
                injury=600,
                initialization_seed=seed,
                enemy_position=(-6, -7, -1),
            )
            if 7944 in granted_spells(fight, 7):
                break
        else:
            self.fail("No actual Miaumiau draw in bounded seeded initialization")
        rng = random.Random(7)
        authority = dict(player_characters=characters, deck_blobs=decks)
        _, adapter = server_runtime(
            characters[7],
            {-7: monster},
            decks[7],
            action_id=10,
            critical=False,
            rng=rng,
            **authority,
        )
        candidates = eligible_cast_targets(
            fight,
            characters[7],
            decks[7],
            7944,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            limit=128,
            maximum_eligible=16,
        )
        enemy_cell = fight.actors[-7].position
        legal_cells = [
            row["target"]
            for row in candidates["eligible"]
            if abs(row["target"][0] - enemy_cell[0])
            + abs(row["target"][1] - enemy_cell[1])
            == 1
        ]
        self.assertTrue(legal_cells, candidates)
        summon_cell = legal_cells[0]
        fight = prepare_server_spell(
            struct.pack(">qqiih", 7, 7944, *summon_cell),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=10,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
            **authority,
        ).fight
        summon = next(
            a
            for a in fight.actors.values()
            if getattr(a, "native_summon_source", None) and a.hp > 0
        )
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **b: prepare_server_turn_end(
                characters[7], {-7: monster}, p, decks[7], rng=rng, **authority, **b
            ),
            turn_start_provider=lambda p, **b: prepare_server_turn_start(
                characters[7], {-7: monster}, p, decks[7], rng=rng, **authority, **b
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                rng=rng,
                **authority,
            )[0],
        )
        for _ in range(20):
            if fight.current is summon:
                break
            advance_actual_turn(runtime)
        self.assertIs(fight.current, summon)
        before = snapshot(fight)
        tx = prepare_server_spell(
            struct.pack(">qqiih", summon.id, 5231, *fight.actors[-7].position),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=20,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
            **authority,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(any(tx.outcomes))
        # 361105 marks the selected enemy; 361106 selects the original
        # controller, then 361108 checks the marker inside its ring 1..3.
        buff = [
            s for s in tx.fight.actors[-7].state_ledger.entries if s.reference == 7957
        ]
        self.assertTrue(buff)
        self.assertEqual(sum(s.level for s in buff), 120)
        self.assertFalse(
            any(s.reference == 7957 for s in tx.fight.actors[8].state_ledger.entries)
        )
