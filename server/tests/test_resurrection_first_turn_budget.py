"""Actual resurrection plus owned resource spend; no raw HP/resource override.

The lethal native damage fixture dispatches an owned NPC effect while actor8 has
not completed its turn. This isolates resurrection budget initialization; it is
not an assertion that NPC AI may take an unsolicited off-turn action.
"""
import os
import random
import struct
import unittest
import test_combat_resurrection_runtime as resurrection_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class ResurrectionFirstTurnBudgetTests(unittest.TestCase):
    def fixture(self):
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health import maximum
        from wakfu_server.spells import encode_deck
        from wakfu_server.monsters import owned_instance

        positions = {
            7: (-8, -7, -1),
            8: (-7, -7, -1),
            9: (-8, -6, -1),
            -7: (-6, -7, -1),
        }
        arena = local_arena(1134, 78, positions[7], positions[-7])
        characters = {
            identity: effective_character(
                dict(
                    id=identity,
                    account_id=identity - 4,
                    map_id=1134,
                    breed=7 if identity == 7 else 8,
                    level=1 if identity == 8 else 60,
                    hp=5 if identity == 8 else maximum(7 if identity == 7 else 8, 60),
                    builds={},
                    inventory_items=[],
                )
            )
            for identity in (7, 8, 9)
        }
        actors = [
            Actor(
                identity,
                0,
                positions[identity],
                characters[identity]["hp"],
                6,
                3,
                initiative,
                characters[identity]["level"],
                characters[identity]["account_id"],
                True,
                max_hp=characters[identity]["max_hp"],
            )
            for identity, initiative in ((7, 30), (8, 20), (9, 10))
        ]
        monster = owned_instance(5525, 1, -7, map_id=1134, x=-6, y=-7, z=-1)
        actors.append(Actor(-7, 1, positions[-7], monster["hp"], 6, 3, 1, 1))
        fight = Fight(
            78,
            actors,
            arena["validated_cells"],
            {0: {positions[7], positions[8], positions[9]}, 1: {positions[-7]}},
            arena["valid_edges"],
        )
        fight.native_qi_snapshot = {
            key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        initialize_global_pv_collections(fight, (7, 8, 9, -7))
        freeze_terrain(fight)
        fight.native_obstacle_cells = frozenset()
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters={-7: monster},
            wp_resources={7: (6, 6), 8: (6, 6), 9: (6, 6), -7: (0, 0)},
            running_effects={identity: () for identity in positions},
            initial_effect_uid=1,
        )
        for owner in (3, 4, 5):
            fight.ready(owner)
        # Iop 4785 is an actual breed-8 level-1 spell; 2050 belongs to Ecaflip.
        decks = {7: encode_deck([1535, 779]), 8: encode_deck([4785]), 9: encode_deck()}
        rng = random.Random(0)
        for action_id, identity in enumerate((7, 8, 9), 1):
            fight, _ = prepare_server_initialization(
                characters[identity],
                {-7: monster},
                fight,
                characters[identity]["account_id"],
                decks[identity],
                action_id=action_id,
                rng=rng,
                fight_start=identity == 9,
                player_characters=characters,
                deck_blobs=decks,
            )
        return fight, characters, monster, decks, rng

    def test_real_resurrection_restores_first_turn_paid_action_budget(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot

        helper = resurrection_fixture.ResurrectionRuntimeTests()
        data = self.fixture()
        fight, characters, monster, decks, rng = data
        runtime = RuntimeMessages(fight)

        def advance():
            actor = runtime.fight.current
            if actor.controlled:
                runtime.end_turn(actor.owner_id, actor.id, actor.turn_count)
            else:
                runtime.end_server_turn(actor.id, runtime.fight.turn_id)
            runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))

        for _ in range(12):
            if runtime.fight.current.id == 8:
                break
            advance()
        self.assertEqual(runtime.fight.current.id, 8)
        victim = runtime.fight.actors[8]
        # Exercise the owned atomic payment API, not a raw characteristic write.
        runtime.fight.spend(4, 8, ap=victim.ap, mp=victim.mp)
        self.assertEqual((victim.ap, victim.mp), (0, 0))
        for index in range(100):
            if runtime.fight.actors[8].hp == 0:
                break
            runtime.fight, _ = helper.damage(
                runtime.fight, characters, monster, decks, rng, 30 + index
            )
        corpse = runtime.fight
        self.assertEqual(corpse.actors[8].hp, 0)
        self.assertNotIn(8, corpse.order)
        # Move the actual timeline to the healer without ending the dead turn.
        for _ in range(12):
            if runtime.fight.current.id == 7:
                break
            advance()
        self.assertEqual(runtime.fight.current.id, 7)
        before = snapshot(runtime.fight)
        result = helper.resurrect(data, runtime.fight, action_id=140)
        self.assertEqual(snapshot(runtime.fight), before)
        runtime.fight = result.fight
        restored_hp = runtime.fight.actors[8].hp
        restored_wp = runtime.fight.actors[8].effect_stats[4]
        self.assertGreater(restored_hp, 0)
        for _ in range(16):
            if runtime.fight.current.id == 8:
                break
            advance()
        self.assertEqual(runtime.fight.current.id, 8)
        restored = runtime.fight.actors[8]
        self.assertEqual((restored.ap, restored.mp), (restored.max_ap, restored.max_mp))
        self.assertEqual(restored.hp, restored_hp)
        self.assertEqual(restored.effect_stats[4], restored_wp)
        before = snapshot(runtime.fight)
        ap = restored.ap
        tx = prepare_server_spell(
            struct.pack(
                ">qqiih", 8, (8 << 32) | 4785, *runtime.fight.actors[-7].position
            ),
            characters[8],
            {-7: monster},
            runtime.fight,
            4,
            decks[8],
            action_id=141,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
            player_characters=characters,
            deck_blobs=decks,
        )
        self.assertTrue(any(tx.outcomes))
        self.assertLess(tx.fight.actors[8].ap, ap)
        self.assertEqual(snapshot(runtime.fight), before)
