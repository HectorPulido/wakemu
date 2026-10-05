"""Full owned gear and native Sacro start enter through production Ready API."""
import unittest
from random import Random
import test_equipment_full_set as fixture
from wakfu_server.equipment_stats import combat_resources
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_wire import arena
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_server_spell import prepare_server_initialization
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class FullSetReadyTests(unittest.TestCase):
    def test_full_set_ready_start_passive_without_partial_source_commit(self):
        character = fixture.FullSetTests().character()
        # Full HP makes native Sacro start children apply legitimate level0
        # states; a wounded-only fixture missed the user's Ready regression.
        character["hp"] = character["max_hp"]
        resources = combat_resources(character)
        cells = [(0, 0, 0), (1, 0, 0)]
        terrain = arena(1134, 1, cells, {0: cells[0], 1: cells[1]})
        terrain["validated_cells"] = cells
        monster = owned_instance(5525, 1, -200, map_id=1134, x=1, y=0, z=0)
        fight, _ = create_placement(
            character,
            monster,
            terrain,
            fight_id=7,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=46,
            terrain_instance_id=1,
        )
        initialize_fight_snapshots(
            fight,
            characters={7: character},
            monsters={-200: monster},
            wp_resources={7: (6, 6), -200: (monster["wp"], monster["wp"])},
            running_effects={7: (), -200: ()},
            initial_effect_uid=1,
        )
        for actor in fight.actors.values():
            actor.direction = 0 if actor.controlled else 3
        deck = encode_deck([5028, 5029, 5030, 5031, 5033, 5034, 5038], [5051])
        before = snapshot(fight)

        def initialize(preview, action_id):
            return prepare_server_initialization(
                character,
                {-200: monster},
                preview,
                3,
                deck,
                action_id=action_id,
                rng=Random(7),
                fight_start=True,
            )

        def stats(actor):
            if actor.controlled:
                return actual_actor_stats(
                    character, actor, 7, wp_current=actor.effect_stats[4], wp_maximum=6
                )
            return actual_monster_actor_stats(
                monster, actor, 7, wp_current=monster["wp"], wp_maximum=monster["wp"]
            )

        started, runtime, packets = prepare_ready(
            fight,
            3,
            True,
            initialize=initialize,
            stats_serializer=stats,
            effects_serializer=actor_effects,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertIn(
            3231, {entry.reference for entry in started.actors[7].state_ledger.entries}
        )
        zero_states = {
            entry.reference
            for entry in started.actors[7].state_ledger.entries
            if entry.level == 0
        }
        self.assertTrue({9312, 9314, 9324}.issubset(zero_states))
        self.assertEqual(started.actors[7].ap, 8)
        self.assertTrue(started.native_start_event_delivered)
        self.assertEqual(started.native_table_turn, 1)
        self.assertIs(runtime.fight, started)
        self.assertIn(13477, [op for op, _ in packets])
        stable = snapshot(started)
        same, messages, empty = prepare_ready(
            started,
            3,
            True,
            initialize=initialize,
            stats_serializer=stats,
            effects_serializer=actor_effects,
        )
        self.assertIs(same, started)
        self.assertEqual((messages, empty), (None, ()))
        self.assertEqual(snapshot(started), stable)
