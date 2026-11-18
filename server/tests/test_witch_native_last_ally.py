"""A single native Witch keeps her last-ally counter with two ordinary allies."""
from copy import deepcopy
import random
import struct
import unittest
from unittest.mock import patch

import test_combat_spell_transaction as spell_fixture


class WitchNativeLastAllyTests(unittest.TestCase):
    def test_three_actor_roster_preserves_native_last_ally_kill(self):
        from wakfu_server.combat_actor_snapshot import (
            initialize_fight_snapshots,
            native_npc_creation_values,
        )
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
        )
        from wakfu_server.spells import encode_deck

        (
            character,
            boss_record,
            base,
        ) = spell_fixture.SpellTransactionTests().native_server_fixture(
            7,
            31,
            native_qi=True,
            target_ref=2096,
            target_level=40,
        )
        actors = []
        for source in base.actors.values():
            actor = Actor(
                source.id,
                source.team,
                source.position,
                source.hp,
                source.ap,
                source.mp,
                source.initiative,
                source.effective_level,
                source.owner_id,
                source.controlled,
                max_hp=source.max_hp,
            )
            actors.append(actor)
        records = {-7: boss_record}
        available = sorted(
            (
                cell
                for cell in base.walkable
                if cell not in {a.position for a in actors}
            ),
            key=lambda p: (
                abs(p[0] - actors[0].position[0]) + abs(p[1] - actors[0].position[1]),
                p,
            ),
        )
        for identity, cell in zip((-8, -9), available):
            values = native_npc_creation_values(2104, 10)
            ally = Actor(
                identity,
                1,
                cell,
                values[1]["current"],
                values[2]["current"],
                values[3]["current"],
                5,
                10,
                max_hp=values[1]["maximum"],
            )
            record = dict(id=identity, ref=2104, map_id=1134)
            actors.append(ally)
            records[identity] = record
        fight = Fight(
            79,
            actors,
            base.walkable,
            {0: {actors[0].position}, 1: {a.position for a in actors[1:]}},
            base.edges,
        )
        fight.native_qi_snapshot = deepcopy(base.native_qi_snapshot)
        fight.native_qi_surface_provenance = deepcopy(base.native_qi_surface_provenance)
        from wakfu_server.combat_geometry_snapshot import freeze_terrain

        freeze_terrain(fight)
        initialize_global_pv_collections(fight, tuple(fight.actors))
        initialize_fight_snapshots(
            fight,
            characters={7: character},
            monsters=records,
            wp_resources={a.id: (6, 6) if a.controlled else (0, 0) for a in actors},
            running_effects={a.id: () for a in actors},
            initial_effect_uid=1,
        )
        fight.ready(3)
        fight.native_obstacle_cells = frozenset()
        deck = encode_deck([630, 779, 645], [])
        rng = random.Random(7)
        fight, _ = prepare_server_initialization(
            character, records, fight, 3, deck, action_id=1, rng=rng, fight_start=True
        )
        self.assertEqual(
            [records[a.id]["ref"] for a in fight.actors.values() if a.team == 1],
            [2096, 2104, 2104],
        )
        self.assertEqual(fight.actors[-7].hp, 5000)
        # Supply the complete original monster mapping to both native turn
        # providers and the actual end-turn/ACK transport boundary.
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from pathlib import Path
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        native_kills = []
        execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            if invocation.reference == 72667:
                native_kills.append((invocation.caster_id, invocation.target_id))
            return execute(dispatcher, invocation, **kwargs)

        def step():
            runtime = RuntimeMessages(
                fight,
                turn_end_provider=lambda p, **b: prepare_server_turn_end(
                    character, records, p, deck, rng=rng, **b
                ),
                turn_start_provider=lambda p, **b: prepare_server_turn_start(
                    character, records, p, deck, rng=rng, **b
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    character,
                    records,
                    deck,
                    action_id=action_id,
                    critical=False,
                    rng=rng,
                )[0],
            )
            with patch.object(EffectDispatcher, "execute", observe):
                advance_actual_turn(runtime)

        for _ in range(8):
            step()
        self.assertGreater(fight.actors[-7].hp, 0)
        self.assertEqual(native_kills, [])
        for identity in (-8, -9):
            while fight.current.id != 7:
                step()
            with patch.object(EffectDispatcher, "execute", observe):
                transaction = prepare_server_spell(
                    struct.pack(
                        ">qqiih", 7, (7 << 32) | 630, *fight.actors[identity].position
                    ),
                    character,
                    records,
                    fight,
                    3,
                    deck,
                    action_id=2,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=rng,
                )
            fight = transaction.fight
            self.assertEqual(fight.actors[identity].hp, 0)
            for _ in range(8):
                if fight.phase == "finished":
                    break
                step()
            if identity == -8:
                self.assertGreater(fight.actors[-7].hp, 0)
                self.assertEqual(native_kills, [])
        self.assertEqual(fight.actors[-7].hp, 0)
        self.assertEqual(native_kills, [(-7, -7)])
        self.assertTrue(
            any(
                e.get("kind") == "death" and e.get("actor_id") == -7
                for e in fight.events
            )
        )
