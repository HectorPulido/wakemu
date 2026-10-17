"""Rogue native Powder, actual bomb ownership and controlled Tymobot lifecycle."""
import os
import random
import struct
import unittest

import test_combat_spell_transaction as native_fixture
import test_aniripsa_grant_summon_pipeline as turns
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_summon_spellbook import actor_action_book
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import available_spells, encode_deck


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RogueRuntimePipelineTests(unittest.TestCase):
    def fixture(self, passives=()):
        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            13,
            200,
            native_qi=True,
            full_health=True,
            target_hp=20000,
            target_distance=3,
            variation_seed=17,
        )
        deck, rng = encode_deck((6463, 6468, 6473), passives), random.Random(17)
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
        fight, _ = prepare_server_turn_start(
            character,
            {-7: monster},
            fight,
            deck,
            actor_id=fight.current.id,
            action_id=2,
            rng=rng,
            area_callbacks=True,
        )
        return character, monster, fight, deck, rng

    @staticmethod
    def powder(fight):
        return [
            entry.level
            for entry in fight.actors[7].state_ledger.entries
            if entry.reference == 7919
        ]

    @staticmethod
    def summons(fight, profiles):
        return [
            actor
            for actor in fight.actors.values()
            if actor.hp > 0
            and getattr(actor, "native_summon_source", None)
            and actor.native_summon_source["ref"] in profiles
        ]

    @staticmethod
    def los(character, origin, target, fight):
        return authoritative_visible(
            character["map_id"],
            origin,
            target,
            fight,
            blocking_footprints={
                actor.id: {actor.position[:2]}
                for actor in fight.actors.values()
                if actor.hp > 0
            },
        )

    def cast(self, data, reference, target=None, *, actor_id=7, action_id=10):
        from class_spell_eligible_targets import eligible_cast_targets

        character, monster, fight, deck, rng = data
        if actor_id == 7:
            grants = granted_spells(fight, actor_id)
            uid = (
                grants[reference]["uid"]
                if reference in grants
                else (actor_id << 32) | reference
            )
        else:
            book = actor_action_book(fight.actors[actor_id])
            action = next(
                row for row in book["actions"] if row["reference"] == reference
            )
            uid = action["uid"]
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=action_id, critical=False, rng=rng
        )
        los = lambda origin, cell, preview: self.los(character, origin, cell, preview)
        if target is None:
            selection = eligible_cast_targets(
                fight,
                character,
                deck,
                uid,
                adapter=adapter,
                line_of_sight=los,
                actor_id=actor_id,
                limit=128,
                maximum_eligible=16,
            )
            self.assertTrue(selection["eligible"], selection)
            target = min(
                selection["eligible"],
                key=lambda row: sum(
                    abs(row["target"][i] - fight.actors[-7].position[i]) for i in (0, 1)
                ),
            )["target"]
        before = snapshot(fight)
        tx = prepare_server_spell(
            struct.pack(">qqiih", actor_id, uid, *target),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=action_id,
            line_of_sight=los,
            critical=None,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(any(tx.outcomes))
        return (*data[:2], tx.fight, *data[3:]), tx

    def test_twenty_owned_passives_initialize_original_grants_and_powder(self):
        passives = [
            row["id"]
            for row in available_spells(13, 200)
            if row["breed"] == 13 and row["kind"] == "passive"
        ]
        self.assertEqual(len(passives), 20)
        for passive in passives:
            with self.subTest(passive=passive):
                data = self.fixture((passive,))
                self.assertEqual(
                    set(granted_spells(data[2], 7)), {6495, 7904, 7905, 7906}
                )
                expected = 1 if passive == 6486 else 5 if passive == 7063 else 3
                self.assertEqual(self.powder(data[2]), [expected])
                self.assertEqual(data[2].actors[7].effect_stats[57], expected)

    def test_four_powder_configurations_pay_real_bomb_and_detonate_once(self):
        for passives, expected in (
            ((), 3),
            ((6486,), 1),
            ((7063,), 5),
            ((6486, 7063), 3),
        ):
            with self.subTest(passives=passives):
                data = self.fixture(passives)
                self.assertEqual(self.powder(data[2]), [expected])
                data, created = self.cast(data, 7906)
                bombs = self.summons(data[2], (3795, 3796, 3797))
                self.assertEqual(len(bombs), 1)
                bomb = bombs[0]
                self.assertEqual(bomb.native_summon_source["caster_id"], 7)
                self.assertEqual(bomb.native_summon_source["controller_id"], 7)
                self.assertGreater(bomb.native_fight_property_counts[114], 0)
                self.assertNotIn(bomb.id, data[2].order)
                self.assertEqual(actor_action_book(bomb)["actions"], [])
                # A zero native amount can remove the resource carrier.
                self.assertEqual(sum(self.powder(data[2])), expected - 1)
                self.assertEqual(data[2].actors[7].effect_stats[57], expected - 1)
                before = snapshot(data[2])
                with self.assertRaises(ValueError):
                    self.cast(data, 6495, data[2].actors[7].position, action_id=11)
                self.assertEqual(snapshot(data[2]), before)
                data, detonated = self.cast(data, 6495, bomb.position, action_id=12)
                self.assertEqual(data[2].actors[bomb.id].hp, 0)
                self.assertFalse(self.summons(data[2], (3795, 3796, 3797)))
                self.assertEqual(sum(self.powder(data[2])), expected)
                self.assertEqual(data[2].actors[7].effect_stats[57], expected)
                before = snapshot(data[2])
                with self.assertRaises(ValueError):
                    self.cast(data, 6495, bomb.position, action_id=13)
                self.assertEqual(snapshot(data[2]), before)

    def test_actual_tymobot_controlled_turn_uses_original_four_action_book(self):
        data = self.fixture()
        data, _ = self.cast(data, 7906)
        bomb = self.summons(data[2], (3795, 3796, 3797))[0]
        data, _ = self.cast(data, 7905, action_id=11)
        robots = self.summons(data[2], (1236,))
        self.assertEqual(len(robots), 1)
        robot = robots[0]
        self.assertEqual(robot.native_summon_source["controller_id"], 7)
        self.assertTrue(robot.controlled)
        book = actor_action_book(robot)
        self.assertEqual(
            {row["reference"] for row in book["actions"]}, {6517, 6520, 7951, 7952}
        )
        helper = turns.AniripsaGrantSummonPipelineTests()
        for _ in range(20):
            if data[2].current.id == robot.id:
                break
            helper.end_current_turn(data[2], data)
        self.assertEqual(data[2].current.id, robot.id)
        self.assertGreater(data[2].actors[robot.id].ap, 0)
        before = snapshot(data[2])
        with self.assertRaises(ValueError):
            self.cast(
                data, 6517, data[2].actors[-7].position, actor_id=robot.id, action_id=20
            )
        self.assertEqual(snapshot(data[2]), before)
        data, tx = self.cast(data, 6517, bomb.position, actor_id=robot.id, action_id=21)
        self.assertTrue(any(tx.outcomes))
        self.assertEqual(
            data[2].actors[robot.id].native_summon_source["controller_id"], 7
        )
