"""Real cast/turn progression reaches Racha for the upgraded Miaumiau branch."""
import os
import random
import struct
import unittest

import test_combat_spell_transaction as native_fixture
import test_aniripsa_grant_summon_pipeline as lifecycle


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipStreakPipelineTests(unittest.TestCase):
    end_current_turn = lifecycle.AniripsaGrantSummonPipelineTests.end_current_turn

    def test_actual_cast_turn_sequence_reaches_streak_and_upgrades_miaumiau(self):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.spells import encode_deck

        for seed in range(24):
            (
                character,
                monster,
                fight,
            ) = native_fixture.SpellTransactionTests().native_server_fixture(
                6, 200, native_qi=True, target_hp=20000, variation_seed=17
            )
            deck = encode_deck((2050, 2079, 7225), (2076,))
            rng = random.Random(seed)
            fight, _ = prepare_server_initialization(
                character,
                {-7: monster},
                fight,
                3,
                deck,
                action_id=1,
                rng=rng,
                fight_start=True,
            )
            if 7944 in granted_spells(fight, 7):
                break
        else:
            self.fail("No actual Miaumiau draw")
        data = character, monster, fight, deck, rng
        for action in range(10, 30):
            level = sum(
                s.level
                for s in fight.actors[7].state_ledger.entries
                if s.reference == 3683
            )
            if level >= 100:
                break
            _, adapter = server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=action,
                critical=False,
                rng=rng,
            )
            candidates = eligible_cast_targets(
                fight,
                character,
                deck,
                (7 << 32) | 2050,
                adapter=adapter,
                line_of_sight=lambda *args: True,
                limit=128,
                maximum_eligible=1,
            )
            if not candidates["eligible"]:
                self.end_current_turn(fight, data)
                for _ in range(20):
                    if fight.current.id == 7:
                        break
                    self.end_current_turn(fight, data)
                self.assertEqual(fight.current.id, 7)
                continue
            fight = prepare_server_spell(
                struct.pack(
                    ">qqiih", 7, (7 << 32) | 2050, *candidates["eligible"][0]["target"]
                ),
                character,
                {-7: monster},
                fight,
                3,
                deck,
                action_id=action,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            ).fight
        level = sum(
            s.level for s in fight.actors[7].state_ledger.entries if s.reference == 3683
        )
        self.assertEqual(level, 100)
        self.assertIn(7944, granted_spells(fight, 7))
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=40, critical=False, rng=rng
        )
        candidates = eligible_cast_targets(
            fight,
            character,
            deck,
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
        fight = prepare_server_spell(
            struct.pack(">qqiih", 7, 7944, *legal_cells[0]),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=40,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        ).fight
        summon = next(
            a
            for a in fight.actors.values()
            if getattr(a, "native_summon_source", None) and a.hp > 0
        )
        book = actor_action_book(summon)
        self.assertEqual(book["profile"], 5535)
        self.assertEqual({row["reference"] for row in book["actions"]}, {7986})
        # 374159 consumes 100; En Racha 359078/359822 then adds 7 for this card.
        self.assertEqual(
            sum(
                s.level
                for s in fight.actors[7].state_ledger.entries
                if s.reference == 3683
            ),
            7,
        )
        for _ in range(20):
            if fight.current is summon:
                break
            self.end_current_turn(fight, data)
        self.assertIs(fight.current, summon)
        tx = prepare_server_spell(
            struct.pack(">qqiih", summon.id, 7986, *fight.actors[-7].position),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=50,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        self.assertEqual(
            sum(
                s.level
                for s in tx.fight.actors[-7].state_ledger.entries
                if s.reference == 7957
            ),
            200,
        )
        self.assertFalse(
            any(s.reference == 7957 for s in tx.fight.actors[7].state_ledger.entries)
        )
