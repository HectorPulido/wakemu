"""Native Ecaflip tarot summons, ability books and actual turn ownership."""
import os
import struct
import unittest

import test_ecaflip_tarot_pipeline as tarot
import test_aniripsa_grant_summon_pipeline as lifecycle


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipSummonPipelineTests(unittest.TestCase):
    fixture = tarot.EcaflipTarotPipelineTests.fixture
    end_current_turn = lifecycle.AniripsaGrantSummonPipelineTests.end_current_turn

    def draw(self, reference, passives):
        from wakfu_server.combat_spell_grant import granted_spells

        for seed in range(24):
            data = self.fixture(seed=seed, passives=passives)
            if reference in granted_spells(data[2], 7):
                return data
        self.fail(f"No actual seeded draw for card {reference}")

    def test_baseline_native_profiles_register_qi_and_exact_ability_books(self):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_summon import fresh_summon_slot_owned
        from wakfu_server.fight_checkpoint_store import snapshot

        for card, passives, profile, abilities in (
            (7944, (), 1482, {5231}),
            # Passive 7955 does not bypass the native Racha >= 100 upgrade.
            (7944, (7955,), 1482, {5231}),
            (7941, (), 3789, set()),
        ):
            with self.subTest(profile=profile):
                data = self.draw(card, passives)
                character, monster, fight, deck, rng = data
                before = snapshot(fight)
                _, adapter = server_runtime(
                    character,
                    {-7: monster},
                    deck,
                    action_id=10,
                    critical=False,
                    rng=rng,
                )
                candidates = eligible_cast_targets(
                    fight,
                    character,
                    deck,
                    card,
                    adapter=adapter,
                    line_of_sight=lambda *args: True,
                    limit=128,
                    maximum_eligible=1,
                )
                self.assertTrue(candidates["eligible"], candidates)
                tx = prepare_server_spell(
                    struct.pack(
                        ">qqiih", 7, card, *candidates["eligible"][0]["target"]
                    ),
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=10,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=rng,
                )
                self.assertEqual(snapshot(fight), before)
                summons = [
                    actor
                    for actor in tx.fight.actors.values()
                    if getattr(actor, "native_summon_source", None) and actor.hp > 0
                ]
                self.assertEqual(len(summons), 1)
                summon = summons[0]
                book = actor_action_book(summon)
                self.assertEqual(book["profile"], profile)
                self.assertEqual(
                    {row["reference"] for row in book["actions"]}, abilities
                )
                self.assertTrue(fresh_summon_slot_owned(tx.fight, summon))
                self.assertIn(summon.id, tx.fight.native_summon_registrations)
                self.assertEqual(summon.team, tx.fight.actors[7].team)
