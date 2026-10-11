"""Native Despertar Silvestre on a real allied roster and lethal NPC event."""
import os
import random
import struct
import unittest

import test_combat_aptitude_healing_runtime as allied


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaAwakeningPipelineTests(unittest.TestCase):
    fixture = allied.AptitudeHealingRuntimeTests.fixture
    setUpClass = allied.AptitudeHealingRuntimeTests.__dict__["setUpClass"]

    def test_actual_npc_ko_then_despertar_restores_owned_ally(self):
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.fight_checkpoint_store import snapshot
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_los import authoritative_visible

        fight, characters, monster, decks = self.fixture(
            active_spells=(5057,),
            caster_breed=10,
            level=200,
            caster_aptitudes=(),
            injury=600,
            enemy_position=(-6, -7, -1),
        )
        authority = dict(player_characters=characters, deck_blobs=decks)
        rng = random.Random(17)
        set_hp_raw_current(fight.actors[8], 1)

        def advance(fight):
            runtime = RuntimeMessages(
                fight,
                turn_end_provider=lambda p, **b: prepare_server_turn_end(
                    characters[7], {-7: monster}, p, decks[7], rng=rng, **authority, **b
                ),
                turn_start_provider=lambda p, **b: prepare_server_turn_start(
                    characters[7], {-7: monster}, p, decks[7], rng=rng, **authority, **b
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    characters[7],
                    {-7: monster},
                    decks[7],
                    action_id=action_id,
                    critical=False,
                    rng=rng,
                    **authority
                )[0],
            )
            advance_actual_turn(runtime)

        for _ in range(20):
            if fight.current.id == -7:
                break
            advance(fight)
        self.assertEqual(fight.current.id, -7)
        target = fight.actors[8]
        source = snapshot(fight)
        tx = prepare_npc_spell(
            fight,
            dict(
                type="cast",
                spellId=7962,
                level=1,
                targetId=8,
                target=list(target.position),
            ),
            characters[7],
            {-7: monster},
            decks[7],
            action_id=20,
            rng=rng,
            **authority
        )
        self.assertEqual(snapshot(fight), source)
        fight = tx.fight
        self.assertEqual(fight.actors[8].hp, 0)
        for _ in range(20):
            if fight.current.id == 7:
                break
            advance(fight)
        self.assertEqual(fight.current.id, 7)

        def los(origin, target, current):
            return authoritative_visible(
                characters[7]["map_id"],
                origin,
                target,
                current,
                blocking_footprints={
                    a.id: {a.position[:2]} for a in current.actors.values() if a.hp > 0
                },
            )

        source = snapshot(fight)
        revived = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 5057, *fight.actors[8].position),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=30,
            line_of_sight=los,
            critical=False,
            rng=rng,
            **authority
        )
        self.assertEqual(snapshot(fight), source)
        self.assertTrue(any(revived.outcomes))
        self.assertGreater(revived.fight.actors[8].hp, 0)
        self.assertIn(
            6505, {s.reference for s in revived.fight.actors[8].state_ledger.entries}
        )
        self.assertGreaterEqual(revived.fight.actors[8].native_obstacle_id, 0)
        current_registry(revived.fight)
