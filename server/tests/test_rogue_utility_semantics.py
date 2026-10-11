"""Owned Rogue utility casts preserve native stance, bomb and team criteria."""
import os
import random
import unittest

import test_combat_spell_transaction as native_fixture
import test_rogue_runtime_pipeline as pipeline
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_turn_start,
)
from wakfu_server.spells import encode_deck


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RogueUtilitySemanticsTests(unittest.TestCase):
    cast = pipeline.RogueRuntimePipelineTests.cast
    los = staticmethod(pipeline.RogueRuntimePipelineTests.los)
    summons = staticmethod(pipeline.RogueRuntimePipelineTests.summons)

    def fixture(self):
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
        deck = encode_deck((6468, 6489, 6490, 6491, 6492, 6493, 6494), ())
        rng = random.Random(17)
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

    def bomb(self, data):
        owner = data[2].actors[7].position
        data, _ = self.cast(data, 7906, (owner[0] + 1, owner[1], owner[2]))
        return data, self.summons(data[2], (3795, 3796, 3797))[0]

    def test_kick_and_magnet_move_the_ring_around_the_owned_bomb(self):
        data, bomb = self.bomb(self.fixture())
        original = bomb.position
        before = {identity: data[2].actors[identity].position for identity in (7, -7)}
        data, _ = self.cast(data, 6490, original, action_id=11)
        # Native360701 crossRing-1-3 excludes its center bomb.
        self.assertEqual(data[2].actors[bomb.id].position, original)
        self.assertTrue(
            any(
                data[2].actors[identity].position != before[identity]
                for identity in before
            )
        )
        ring_after_kick = {
            identity: data[2].actors[identity].position for identity in (7, -7)
        }
        data, _ = self.cast(data, 6493, original, action_id=12)
        # Native307172 attracts the surrounding actors, not its center bomb.
        self.assertEqual(data[2].actors[bomb.id].position, original)
        self.assertTrue(
            any(
                data[2].actors[identity].position != ring_after_kick[identity]
                for identity in ring_after_kick
            )
        )
        self.assertEqual(
            data[2].actors[bomb.id].native_summon_source["controller_id"], 7
        )

    def test_evanescence_uses_an_actual_owned_bomb(self):
        data, bomb = self.bomb(self.fixture())
        original = data[2].actors[7].position
        data, _ = self.cast(data, 6491, bomb.position, action_id=11)
        self.assertNotEqual(data[2].actors[7].position, original)

    def test_hook_uses_the_stance_of_a_real_earth_attack(self):
        data = self.fixture()
        data, _ = self.cast(data, 6468, data[2].actors[-7].position)
        original = data[2].actors[7].position
        data, _ = self.cast(data, 6492, data[2].actors[-7].position, action_id=11)
        # Distant stance7916 uses native305 to move the caster.
        self.assertNotEqual(data[2].actors[7].position, original)

    def test_smoke_distinguishes_actual_enemy_and_friendly_recipients(self):
        for actor_id, state in ((-7, 6877), (7, 5627)):
            with self.subTest(actor_id=actor_id):
                data = self.fixture()
                data, _ = self.cast(data, 6494, data[2].actors[actor_id].position)
                self.assertIn(
                    state,
                    {
                        row.reference
                        for row in data[2].actors[actor_id].state_ledger.entries
                    },
                )

    def test_unloader_counts_actual_owned_bombs_into_the_caster_marker(self):
        data, bomb = self.bomb(self.fixture())
        sequence = data[2].sequence
        data, _ = self.cast(data, 6489, data[2].actors[7].position, action_id=11)
        # Native395068 uses SELF8194;395073 uses SELF+area8195.
        applied = {
            (row["actor_id"], row["state_id"])
            for row in data[2].events
            if row["kind"] == "state_applied" and row["sequence"] > sequence
        }
        self.assertIn((7, 8894), applied)
        self.assertIn((7, 7934), applied)
