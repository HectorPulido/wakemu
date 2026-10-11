"""Native Peace Armor grant, legal teleport and actual timed grant retirement."""
import os
import random
import struct
import unittest
import test_combat_aptitude_healing_runtime as allied


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class FecaGrantPipelineTests(unittest.TestCase):
    fixture = allied.AptitudeHealingRuntimeTests.fixture
    setUpClass = allied.AptitudeHealingRuntimeTests.__dict__["setUpClass"]

    def test_peace_armor_grants_teleport_and_retires_it_on_actual_expiry(self):
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.fight_checkpoint_store import snapshot
        from combat_audit_turns import advance_actual_turn

        fight, characters, monster, decks = self.fixture(
            active_spells=(6972,),
            caster_breed=1,
            level=200,
            caster_aptitudes=(),
            enemy_position=(-8, -9, -1),
        )
        rng = random.Random(7)
        self.assertEqual(set(granted_spells(fight, 7)), {7009})

        def cast(spell, cell, action_id):
            return prepare_server_spell(
                struct.pack(">qqiih", 7, spell, *cell),
                characters[7],
                {-7: monster},
                fight,
                3,
                decks[7],
                action_id=action_id,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
                player_characters=characters,
                deck_blobs=decks,
            )

        before = snapshot(fight)
        armor = cast(7009, fight.actors[7].position, 10)
        self.assertEqual(snapshot(fight), before)
        fight = armor.fight
        self.assertIn(6364, {s.reference for s in fight.actors[7].state_ledger.entries})
        self.assertEqual(set(granted_spells(fight, 7)), {7009, 7052})
        self.assertEqual(granted_spells(fight, 7)[7052]["level"], 1)
        self.assertEqual(armor.plan["costs"]["ap"], 2)
        self.assertEqual(armor.plan["costs"]["wp"], 1)
        teleport = cast(7052, (-8, -8, -1), 11)
        self.assertEqual(teleport.fight.actors[7].position, (-8, -8, -1))
        self.assertEqual(teleport.plan["costs"]["ap"], 0)
        self.assertEqual(teleport.plan["costs"]["wp"], 1)
        runtime = RuntimeMessages(
            teleport.fight,
            turn_end_provider=lambda p, **b: prepare_server_turn_end(
                characters[7],
                {-7: monster},
                p,
                decks[7],
                rng=rng,
                player_characters=characters,
                deck_blobs=decks,
                **b
            ),
            turn_start_provider=lambda p, **b: prepare_server_turn_start(
                characters[7],
                {-7: monster},
                p,
                decks[7],
                rng=rng,
                area_callbacks=True,
                player_characters=characters,
                deck_blobs=decks,
                **b
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                rng=rng,
                player_characters=characters,
                deck_blobs=decks,
            )[0],
        )
        for _ in range(12):
            advance_actual_turn(runtime)
        self.assertNotIn(
            6364, {s.reference for s in runtime.fight.actors[7].state_ledger.entries}
        )
        self.assertEqual(set(granted_spells(runtime.fight, 7)), {7009})
        self.assertEqual(runtime.fight.phase, "active")
