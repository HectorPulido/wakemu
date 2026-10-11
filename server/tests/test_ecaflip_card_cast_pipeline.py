"""Actual seeded native Ecaflip card grants, casts and retirement."""
import os
import struct
import unittest

import test_ecaflip_tarot_pipeline as tarot


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipCardCastPipelineTests(tarot.EcaflipTarotPipelineTests):
    # Keep inherited setup helpers, but do not duplicate their test methods.
    test_actual_ready_draws_distinct_owned_cards_with_native_hand_cap = None
    test_optional_passives_initialize_without_duplicate_or_foreign_grants = None

    def test_all_thirteen_cards_cast_from_actual_draws_and_retire_owned_grants(self):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.fight_checkpoint_store import snapshot

        covered = set()
        expected = set(range(7938, 7951))
        for seed in range(24):
            character, monster, fight, deck, rng = self.fixture(
                seed=seed,
                passives=(2068, 2080, 5250),
            )
            for reference in sorted(set(granted_spells(fight, 7)) & expected - covered):
                with self.subTest(seed=seed, card=reference):
                    original = snapshot(fight)
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
                        reference,
                        adapter=adapter,
                        line_of_sight=lambda *args: True,
                        limit=128,
                        maximum_eligible=1,
                    )
                    self.assertTrue(candidates["eligible"], candidates)
                    cell = candidates["eligible"][0]["target"]
                    tx = prepare_server_spell(
                        struct.pack(">qqiih", 7, reference, *cell),
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
                    self.assertEqual(snapshot(fight), original)
                    self.assertTrue(any(tx.outcomes))
                    self.assertNotIn(reference, granted_spells(tx.fight, 7))
                    # The native 1024 listener removes the grant effect, not
                    # its card carrier. Mala Suerte later selects these played
                    # carriers by HasState and absence of their grant effect.
                    self.assertTrue(
                        any(
                            entry.reference == reference + 23
                            for entry in tx.fight.actors[7].state_ledger.entries
                        )
                    )
                    counter = next(
                        entry.level
                        for entry in tx.fight.actors[7].state_ledger.entries
                        if entry.reference == 7941
                    )
                    self.assertEqual(counter, 3)
                    # Card 7947 executes native AP producer 374041 (+3).
                    produced_ap = 3 if reference == 7947 else 0
                    self.assertEqual(
                        tx.fight.actors[7].ap,
                        fight.actors[7].ap - tx.plan["costs"]["ap"] + produced_ap,
                    )
                    covered.add(reference)
            if covered == expected:
                break
        self.assertEqual(covered, expected)
