"""Actual flea regeneration/spread and Felintuicion area ownership lifecycle."""
import os
import random
import struct
import unittest

import test_combat_aptitude_healing_runtime as allied


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipFleaLifecyclePipelineTests(unittest.TestCase):
    fixture = allied.AptitudeHealingRuntimeTests.fixture
    setUpClass = allied.AptitudeHealingRuntimeTests.__dict__["setUpClass"]

    def advance(self, fight, characters, monster, decks):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from combat_audit_turns import advance_actual_turn

        def context(preview):
            identity = preview.current.id
            identity = identity if identity in characters else 7
            return characters[identity], decks[identity]

        def end(preview, **boundary):
            character, deck = context(preview)
            return prepare_server_turn_end(
                character,
                {-7: monster},
                preview,
                deck,
                rng=random.Random(0),
                player_characters=characters,
                deck_blobs=decks,
                **boundary
            )

        def start(preview, **boundary):
            character, deck = context(preview)
            return prepare_server_turn_start(
                character,
                {-7: monster},
                preview,
                deck,
                rng=random.Random(0),
                player_characters=characters,
                deck_blobs=decks,
                area_callbacks=True,
                **boundary
            )

        character, deck = context(fight)
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=end,
            turn_start_provider=start,
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=action_id,
                critical=False,
                rng=random.Random(0),
                player_characters=characters,
                deck_blobs=decks,
            )[0],
        )
        advance_actual_turn(runtime)
        return runtime.fight

    def cast(self, fight, characters, monster, decks, reference, target):
        from wakfu_server.combat_server_spell import prepare_server_spell

        return prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | reference, *target),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=10,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(7),
            player_characters=characters,
            deck_blobs=decks,
        ).fight

    def test_actual_fleas_heal_at_recipient_end_and_spread_only_to_allies(self):
        fight, characters, monster, decks = self.fixture(
            active_spells=(2067,),
            passive_spells=(2062,),
            caster_breed=6,
            level=200,
            caster_aptitudes=(),
            injury=600,
        )
        fight = self.cast(
            fight, characters, monster, decks, 2067, fight.actors[8].position
        )
        self.assertEqual(
            sum(
                e.level
                for e in fight.actors[8].state_ledger.entries
                if e.reference == 3697
            ),
            26,
        )
        while fight.current.id != 8:
            fight = self.advance(fight, characters, monster, decks)
        before_hp = fight.actors[8].hp
        fight = self.advance(fight, characters, monster, decks)
        self.assertGreater(fight.actors[8].hp, before_hp)
        self.assertFalse(
            any(e.reference == 3697 for e in fight.actors[-7].state_ledger.entries)
        )
        self.assertTrue(
            any(
                e.reference == 3697
                for identity in (7, 9)
                for e in fight.actors[identity].state_ledger.entries
            )
        )

    def test_actual_felintuicion_area_is_owned_and_expires_without_dangling_record(
        self,
    ):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import server_runtime

        fight, characters, monster, decks = self.fixture(
            active_spells=(2061,),
            caster_breed=6,
            level=200,
            caster_aptitudes=(),
            injury=600,
        )
        _, adapter = server_runtime(
            characters[7],
            {-7: monster},
            decks[7],
            action_id=10,
            critical=False,
            rng=random.Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )
        candidates = eligible_cast_targets(
            fight,
            characters[7],
            decks[7],
            (7 << 32) | 2061,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            limit=128,
            maximum_eligible=1,
        )
        self.assertTrue(candidates["eligible"], candidates)
        fight = self.cast(
            fight, characters, monster, decks, 2061, candidates["eligible"][0]["target"]
        )
        areas = {
            uid: row
            for uid, row in fight.native_effect_areas.items()
            if row["reference"] == 1798
        }
        self.assertTrue(areas)
        self.assertTrue(all(row["owner_id"] == 7 for row in areas.values()))
        for _ in range(32):
            if not set(areas).intersection(fight.native_effect_areas):
                break
            fight = self.advance(fight, characters, monster, decks)
        self.assertFalse(set(areas).intersection(fight.native_effect_areas))
        self.assertFalse(
            set(areas).intersection(
                row["manager_id"] for row in fight.native_retained_records.values()
            )
        )
