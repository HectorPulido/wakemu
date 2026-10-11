"""A different real allied player is excluded from the Hot Wheels enemy guard."""
import os
import random
import struct
import unittest
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerFriendlyMicrobotRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_combat_aptitude_healing_runtime import AptitudeHealingRuntimeTests

        AptitudeHealingRuntimeTests.setUpClass()
        cls.fixture_factory = AptitudeHealingRuntimeTests

    def test_other_owned_allied_player_entry_and_turn_do_not_trigger_enemy_damage(self):
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from tools.combat_audit_turns import advance_actual_turn

        fight, characters, monster, decks = self.fixture_factory().fixture(
            caster_breed=16,
            level=200,
            caster_aptitudes=(),
            injury=0,
            active_spells=(),
            passive_spells=(6940,),
            compact_arena=False,
        )
        self.assertNotEqual(fight.actors[7].id, fight.actors[8].id)
        self.assertEqual(fight.actors[7].team, fight.actors[8].team)
        origin = fight.actors[8].position
        entry = (origin[0], origin[1] + 1, origin[2])
        self.assertIn(entry, fight.walkable)
        self.assertNotIn(entry, {a.position for a in fight.actors.values()})
        rng = random.Random(0)
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        born = prepare_server_spell(
            struct.pack(">qqiih", 7, granted_spells(fight, 7)[7008]["uid"], *entry),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=10,
            line_of_sight=lambda *args: True,
            critical=False,
            **common
        )
        fight = born.fight
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **b: prepare_server_turn_end(
                characters[7], {-7: monster}, p, decks[7], **common, **b
            ),
            turn_start_provider=lambda p, **b: prepare_server_turn_start(
                characters[7], {-7: monster}, p, decks[7], **common, **b
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
        # Native initiative interleaves the opposing team; reach the allied
        # player through real end/ACK boundaries instead of assuming roster order.
        for _ in range(len(fight.actors) + 1):
            if fight.current.id == 8:
                break
            advance_actual_turn(runtime)
        self.assertEqual(fight.current.id, 8)
        before = fight.actors[8].hp
        trace = []
        execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (343996, 343998, 344433, 344434):
                trace.append((invocation.reference, invocation.target_id, result))
            return result

        with patch.object(EffectDispatcher, "execute", observe):
            fight.move(4, 8, [entry])
            fight, _ = prepare_area_movement(
                characters[8],
                {-7: monster},
                fight,
                decks[8],
                actor_id=8,
                action_id=30,
                path=[entry],
                origin=origin,
                **common
            )
            runtime.fight = fight
            advance_actual_turn(runtime)
        self.assertFalse(
            any(ok for ref, _, ok in trace if ref in (343998, 344433, 344434)), trace
        )
        self.assertGreaterEqual(fight.actors[8].hp, before, trace)
