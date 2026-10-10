"""Positive Aniripsa utility consequences using real Ready and turn producers."""
import os
import random
import struct
import unittest
from unittest.mock import patch

import test_aniripsa_utility_pipeline as utility


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class AniripsaUtilityTriggerTests(unittest.TestCase):
    fixture = utility.AniripsaUtilityPipelineTests.fixture
    make = utility.AniripsaUtilityPipelineTests.make
    cast = utility.AniripsaUtilityPipelineTests.cast
    setUpClass = utility.AniripsaUtilityPipelineTests.__dict__["setUpClass"]

    def test_prohibicion_consumes_real_ready_armor_and_heals_caster(self):
        from wakfu_server.equipment_stats import effective_character
        from tests.test_aptitude_catalog_coverage import aptitude_sheet

        def armored_character(row, *args, **kwargs):
            if row["id"] == 8:
                row["builds"][0]["aptitudes"] = aptitude_sheet([(36, 2)]).hex()
            return effective_character(row, *args, **kwargs)

        with patch(
            "wakfu_server.equipment_stats.effective_character", armored_character
        ):
            fixture = self.make(1538)
        original = fixture[0].actors[8]
        self.assertGreater(original.effect_stats[97], 0)
        result = self.cast(fixture, 1538, 8)
        target = result.fight.actors[8]
        self.assertEqual((original.effect_stats[97], target.effect_stats[97]), (196, 0))
        self.assertEqual(result.fight.actors[7].hp - fixture[0].actors[7].hp, 245)
        self.assertEqual(target.hp, original.hp)
        self.assertLess(target.effect_stats[97], original.effect_stats[97])
        self.assertGreater(result.fight.actors[7].hp, fixture[0].actors[7].hp)
        self.assertLessEqual(target.hp, target.max_hp)

    def test_gangrena_real_target_turn_end_deals_damage_and_returns_life(self):
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )

        fixture = self.make(1542)
        result = self.cast(fixture, 1542, 8)
        _, characters, monster, decks = fixture
        original_hp = result.fight.actors[8].hp
        original_caster_hp = result.fight.actors[7].hp
        common = dict(
            player_characters=characters, deck_blobs=decks, rng=random.Random(0)
        )
        runtime = RuntimeMessages(
            result.fight,
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                **common
            )[0],
        )
        seen_target = False
        for _ in range(8):
            ended = runtime.fight.current.id
            advance_actual_turn(runtime)
            if ended == 8:
                seen_target = True
                break
        self.assertTrue(seen_target)
        self.assertEqual(original_hp - runtime.fight.actors[8].hp, 84)
        self.assertEqual(runtime.fight.actors[7].hp - original_caster_hp, 83)
        self.assertLess(runtime.fight.actors[8].hp, original_hp)
        self.assertGreater(runtime.fight.actors[7].hp, original_caster_hp)

    def test_colimador_collision_adds_damage_to_real_granted_repulsion(self):
        from wakfu_server.combat_qi_fight import move_registered_actor
        from wakfu_server.combat_server_spell import prepare_server_spell

        losses = []
        for colimador in (False, True):
            fixture = self.make(623, enemy_position=(-9, -7, -1))
            fight, characters, monster, decks = fixture
            # Occupied validated QI cell blocks the real displacement, without
            # synthesizing a collision event or editing combat resources.
            move_registered_actor(fight, fight.actors[9], (-10, -7, -1))
            if colimador:
                fight = self.cast(fixture, 623, -7).fight
            hp = fight.actors[-7].hp
            result = prepare_server_spell(
                struct.pack(">qqiih", 7, 7979, *fight.actors[-7].position),
                characters[7],
                {-7: monster},
                fight,
                3,
                decks[7],
                action_id=11,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=random.Random(0),
                player_characters=characters,
                deck_blobs=decks,
            )
            losses.append(hp - result.fight.actors[-7].hp)
            self.assertEqual(
                result.fight.actors[-7].position, fight.actors[-7].position
            )
        self.assertEqual(losses, [0, 25])
        self.assertGreater(losses[1], losses[0])
