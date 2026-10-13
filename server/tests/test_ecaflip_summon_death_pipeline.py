"""Real owned NPC damage retires Ecaflip summons and releases QI occupancy."""
import os
import struct
import unittest

import test_ecaflip_summon_pipeline as summons


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipSummonDeathPipelineTests(unittest.TestCase):
    fixture = summons.EcaflipSummonPipelineTests.fixture
    draw = summons.EcaflipSummonPipelineTests.draw
    end_current_turn = summons.EcaflipSummonPipelineTests.end_current_turn

    def test_actual_npc_lethal_hit_releases_miaumiau_qi(self):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.fight_checkpoint_store import snapshot

        data = self.draw(7944, ())
        character, monster, fight, deck, rng = data
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=10, critical=False, rng=rng
        )
        eligible = eligible_cast_targets(
            fight,
            character,
            deck,
            7944,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            limit=128,
            maximum_eligible=16,
        )
        enemy = fight.actors[-7]
        cells = [
            row["target"]
            for row in eligible["eligible"]
            if abs(row["target"][0] - enemy.position[0])
            + abs(row["target"][1] - enemy.position[1])
            == 1
        ]
        self.assertTrue(cells, eligible)
        fight = prepare_server_spell(
            struct.pack(">qqiih", 7, 7944, *cells[0]),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=10,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        ).fight
        summon = next(
            a
            for a in fight.actors.values()
            if getattr(a, "native_summon_source", None) and a.hp > 0
        )
        set_hp_raw_current(summon, 1)
        for _ in range(20):
            if fight.current.id == -7:
                break
            self.end_current_turn(fight, data)
        self.assertEqual(fight.current.id, -7)
        owner_hp_before = fight.actors[7].hp
        source = snapshot(fight)
        tx = prepare_npc_spell(
            fight,
            dict(
                type="cast",
                spellId=7962,
                level=1,
                targetId=summon.id,
                target=list(summon.position),
            ),
            character,
            {-7: monster},
            deck,
            action_id=20,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), source)
        dead = tx.fight.actors[summon.id]
        self.assertEqual(dead.hp, 0)
        # Native Bow Meow life link copies incoming damage to its Ecaflip.
        self.assertLess(tx.fight.actors[7].hp, owner_hp_before)
        self.assertEqual(fight.actors[7].hp, owner_hp_before)
        self.assertEqual(dead.native_obstacle_id, -1)
        current_registry(tx.fight)
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_summon import fresh_summon_slot_owned

        fight = tx.fight
        for _ in range(12):
            for _ in range(20):
                self.end_current_turn(fight, data)
                if fight.current.id == 7:
                    break
            self.assertEqual(fight.current.id, 7)
            if 7944 not in granted_spells(fight, 7):
                # Mala Suerte2079 recovers the genuinely played carrier.
                # Doble o Nada2060 auto-plays cards and cannot replenish grants.
                try:
                    fight = prepare_server_spell(
                        struct.pack(
                            ">qqiih", 7, (7 << 32) | 2079, *fight.actors[7].position
                        ),
                        character,
                        {-7: monster},
                        fight,
                        3,
                        deck,
                        action_id=30,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=rng,
                    ).fight
                except ValueError as error:
                    if "cast interval has not elapsed" not in str(error):
                        raise
                    continue  # Advance real turns until native interval permits played-card recovery.
                if 7944 not in granted_spells(fight, 7):
                    continue
            _, adapter = server_runtime(
                character, {-7: monster}, deck, action_id=40, critical=False, rng=rng
            )
            eligible = eligible_cast_targets(
                fight,
                character,
                deck,
                7944,
                adapter=adapter,
                line_of_sight=lambda *args: True,
                limit=128,
                maximum_eligible=16,
            )
            if cells[0] not in [row["target"] for row in eligible["eligible"]]:
                continue
            replacement = prepare_server_spell(
                struct.pack(">qqiih", 7, 7944, *cells[0]),
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
            living = [
                a
                for a in replacement.actors.values()
                if getattr(a, "native_summon_source", None) and a.hp > 0
            ]
            self.assertEqual(len(living), 1)
            self.assertNotEqual(living[0].id, summon.id)
            self.assertTrue(fresh_summon_slot_owned(replacement, living[0]))
            current_registry(replacement)
            return
        self.fail("No legal actual redraw/resummon within bounded twelve turns")
