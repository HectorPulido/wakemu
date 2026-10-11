"""Anisurreccion on a real allied corpse, through owned native dispatch."""
import os
import random
import struct
import unittest
from copy import deepcopy
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class ResurrectionRuntimeTests(unittest.TestCase):
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
        decks = {7: encode_deck([1535, 779]), 8: encode_deck(), 9: encode_deck()}
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

    def damage(self, fight, characters, monster, decks, rng, action_id):
        from wakfu_server.combat_npc_attack import (
            ability,
            npc_runtime_catalog,
            npc_spell_catalog,
        )
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_los import static_visible

        preview = deepcopy(fight)
        source, target = preview.actors[-7], preview.actors[8]
        rule = ability(monster)
        self.assertEqual(
            abs(source.position[0] - target.position[0])
            + abs(source.position[1] - target.position[1]),
            1,
        )
        self.assertTrue(static_visible(1134, source.position, target.position))
        factory, _ = server_runtime(
            characters[7],
            {-7: monster},
            decks[7],
            action_id=action_id,
            critical=False,
            rng=rng,
            compiled=npc_runtime_catalog(),
            player_characters=characters,
            deck_blobs=decks,
        )
        dispatcher, packets = factory(
            preview,
            dict(
                actor_id=-7,
                spell_id=rule["spell_id"],
                evaluation_level=rule["spell_level"],
                target_id=8,
                target=target.position,
                costs={key: rule[key] for key in ("ap", "mp", "wp")},
            ),
        )
        with preview.effect_resolution():
            for reference in npc_spell_catalog()["spells"][str(rule["spell_id"])][
                "levels"
            ][rule["spell_level"] - 1][2]:
                dispatcher.execute(
                    EffectInvocation(
                        reference,
                        rule["spell_level"],
                        -7,
                        8,
                        target.position,
                        native_explicit_target=True,
                    )
                )
        return preview, packets

    def resurrect(self, fixture, fight, action_id=6):
        from wakfu_server.combat_server_spell import prepare_server_spell

        _, characters, monster, decks, rng = fixture
        return prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 1535, *fight.actors[8].position),
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

    def test_actual_ally_death_resurrection_and_failed_child_rollback(self):
        from wakfu_server.combat_global_pv_collections import global_fighter_guards
        from wakfu_server.combat_native_death_status import native_is_dead
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_death import death_messages
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.fight_checkpoint_store import snapshot

        fixture = self.fixture()
        original, characters, monster, decks, rng = fixture
        corpse = original
        for index in range(100):
            if corpse.actors[8].hp == 0:
                break
            previous_hp = corpse.actors[8].hp
            corpse, _ = self.damage(corpse, characters, monster, decks, rng, 4 + index)
            self.assertLess(corpse.actors[8].hp, previous_hp)
        self.assertEqual(corpse.actors[8].hp, 0)
        self.assertTrue(global_fighter_guards(corpse, 8)["baG"])
        self.assertNotIn(8, corpse.order)
        runtime = RuntimeMessages(corpse)
        runtime.prepare_delivery(death_messages(runtime, 8))
        self.assertIn(8, runtime._reported_deaths)
        before = snapshot(corpse)
        rng_before = rng.getstate()
        execute = EffectDispatcher.execute

        def fail_child(dispatcher, invocation, **kwargs):
            if invocation.reference == 166895:
                raise ValueError("interrupted resurrection carrier")
            return execute(dispatcher, invocation, **kwargs)

        with patch.object(EffectDispatcher, "execute", fail_child):
            with self.assertRaisesRegex(ValueError, "interrupted resurrection carrier"):
                self.resurrect(fixture, corpse)
        self.assertEqual(snapshot(corpse), before)
        self.assertEqual(rng.getstate(), rng_before)
        result = self.resurrect(fixture, corpse)
        self.assertEqual(snapshot(corpse), before)
        restored = result.fight.actors[8]
        self.assertGreater(restored.hp, 0)
        self.assertEqual(
            global_fighter_guards(result.fight, 8), dict(baF=True, baG=False, baK=False)
        )
        self.assertFalse(native_is_dead(restored))
        self.assertIn(8, result.fight.order)
        removed_position = next(
            row["position"]
            for row in corpse.native_timeline_removed
            if row["actor_id"] == 8
        )
        self.assertEqual(
            result.fight.native_timeline_member_counters["8"],
            corpse.native_timeline_round
            + (min(removed_position, len(corpse.order)) <= corpse.turn_index),
        )
        self.assertEqual(result.fight.order.count(8), 1)
        if result.fight.native_base_turn_order is not None:
            self.assertEqual(result.fight.native_base_turn_order.count(8), 1)
        self.assertEqual(result.fight.current.id, corpse.current.id)
        self.assertFalse(
            any(row["actor_id"] == 8 for row in result.fight.native_timeline_removed)
        )
        self.assertIn(
            1144, {state.reference for state in restored.state_ledger.entries}
        )
        registry = current_registry(result.fight)
        self.assertIn(
            restored.native_obstacle_id, registry.ordered_U(*restored.position[:2])
        )
        self.assertTrue(
            any(op == 12727 and body[-1] == 1 for op, body in result.packets)
        )
        runtime.fight = result.fight
        runtime.prepare_delivery(result.packets)
        self.assertNotIn(8, runtime._reported_deaths)
        # The restored fighter legitimately rejoins the next turn cycle.
        while runtime.fight.current.id != 8:
            actor = runtime.fight.current
            if actor.controlled:
                runtime.end_turn(actor.owner_id, actor.id, actor.turn_count)
            else:
                runtime.end_server_turn(actor.id, runtime.fight.turn_id)
            runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
        # An owned next-turn request succeeds with its actual turn counter.
        runtime.end_turn(4, 8, runtime.fight.current.turn_count)
        runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
        # Actual native ability applications, never a fabricated HP-zero write.
        for index in range(30):
            if runtime.fight.actors[8].hp == 0:
                break
            runtime.fight, _ = self.damage(
                runtime.fight, characters, monster, decks, rng, 8 + index
            )
        self.assertEqual(runtime.fight.actors[8].hp, 0)
        second_death = runtime.prepare_delivery(death_messages(runtime, 8))
        # Native aTS fighter state 0 preserves reversible player KO and QI.
        self.assertTrue(any(op == 12727 and body[-1] == 0 for op, body in second_death))
