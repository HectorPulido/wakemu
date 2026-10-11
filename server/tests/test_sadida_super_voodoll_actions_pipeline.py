"""Actual Superpoderosa attack and Voodoll owned-doll swap."""
import os
import struct
import unittest

import test_sadida_grant_pipeline as grants
import test_aniripsa_grant_summon_pipeline as turns


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaSuperVoodollActionsPipelineTests(unittest.TestCase):
    fixture = grants.SadidaGrantPipelineTests.fixture
    cast = grants.SadidaGrantPipelineTests.cast

    def summon_cast(self, data, actor_id, reference, target):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.fight_checkpoint_store import snapshot

        character, monster, fight, deck, rng, _ = data
        helper = turns.AniripsaGrantSummonPipelineTests()
        for _ in range(30):
            if fight.current.id == actor_id:
                break
            helper.end_current_turn(fight, data[:5])
        self.assertEqual(fight.current.id, actor_id)
        uid = next(
            row["uid"]
            for row in actor_action_book(fight.actors[actor_id])["actions"]
            if row["reference"] == reference
        )

        def los(origin, destination, current):
            return authoritative_visible(
                character["map_id"],
                origin,
                destination,
                current,
                blocking_footprints={
                    a.id: {a.position[:2]} for a in current.actors.values() if a.hp > 0
                },
            )

        before = snapshot(fight)
        tx = prepare_server_spell(
            struct.pack(">qqiih", actor_id, uid, *target),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=40,
            line_of_sight=los,
            critical=False,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(any(tx.outcomes))
        return tx

    def test_actual_superpoderosa_5153_damages_enemy(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book

        data = self.fixture()
        seeded = self.cast(data, 8137)
        data = (*data[:2], seeded.fight, *data[3:])
        cell = next(
            a["cell"]
            for a in data[2].native_effect_areas.values()
            if a["reference"] == 1835
        )
        doll = self.cast(data, 925, target=cell, action_id=11)
        data = (*data[:2], doll.fight, *data[3:])
        turns.AniripsaGrantSummonPipelineTests().next_player_turn(data[2], data[:5])
        born = self.cast(data, 911, target=(-7, -7, -1), action_id=12)
        data = (*data[:2], born.fight, *data[3:])
        actor = next(
            a
            for a in data[2].actors.values()
            if getattr(a, "native_summon_source", None)
            and a.hp > 0
            and actor_action_book(a)["profile"] == 3746
        )
        hp = data[2].actors[-7].hp
        tx = self.summon_cast(data, actor.id, 5153, data[2].actors[-7].position)
        self.assertLess(tx.fight.actors[-7].hp, hp)

    def test_actual_voodoll_8140_swaps_with_owned_doll(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book

        data = self.fixture()
        vudul = self.cast(data, 926)
        data = (*data[:2], vudul.fight, *data[3:])
        turns.AniripsaGrantSummonPipelineTests().next_player_turn(data[2], data[:5])
        seeded = self.cast(data, 8137)
        data = (*data[:2], seeded.fight, *data[3:])
        cell = next(
            a["cell"]
            for a in data[2].native_effect_areas.values()
            if a["reference"] == 1835
        )
        born = self.cast(data, 925, target=cell, action_id=12)
        data = (*data[:2], born.fight, *data[3:])
        pets = {
            actor_action_book(a)["profile"]: a
            for a in data[2].actors.values()
            if getattr(a, "native_summon_source", None) and a.hp > 0
        }
        source, target = pets[3745], pets[3747]
        positions = source.position, target.position
        tx = self.summon_cast(data, source.id, 8140, target.position)
        self.assertEqual(tx.fight.actors[source.id].position, positions[1])
        self.assertEqual(tx.fight.actors[target.id].position, positions[0])
