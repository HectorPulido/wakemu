"""Native Ouginak Wauwau summon, owned action book and retirement lifecycle."""
import os
import struct
import unittest
from random import Random
from unittest.mock import patch

from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_end,
)
from wakfu_server.combat_summon_retirement import retired_summon_ids
from wakfu_server.combat_summon_spellbook import actor_spellbook
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.equipment_stats import effective_character, combat_resources
from wakfu_server.health import maximum
from wakfu_server.spells import encode_deck


@patch.dict(
    os.environ,
    {"WAKFU_NATIVE_GRANTED_CAST": "1", "WAKFU_NATIVE_AREA_CALLBACKS": "1"},
)
class WauwauLifecycleTests(unittest.TestCase):
    def fixture(self):
        origin = (-4, -18, 0)
        enemy_position = (-2, -18, 0)
        characters = {}
        decks = {}
        actors = []
        wp_resources = {}
        for identity, account, team, level, position, active in (
            (7, 3, 0, 90, origin, []),
            (8, 4, 1, 200, enemy_position, [6261, 6266]),
        ):
            character = effective_character(
                dict(
                    id=identity,
                    account_id=account,
                    breed=15,
                    level=level,
                    hp=maximum(15, level),
                    max_hp=maximum(15, level),
                    map_id=1134,
                    builds={},
                    inventory_items=[],
                )
            )
            resources = combat_resources(character)
            characters[identity] = character
            decks[identity] = encode_deck(active)
            actors.append(
                Actor(
                    identity,
                    team,
                    position,
                    character["hp"],
                    resources["ap"],
                    resources["mp"],
                    resources["initiative"],
                    level,
                    account,
                    True,
                    max_hp=character["max_hp"],
                )
            )
            wp_resources[identity] = (resources["wp"], resources["wp"])
        characters[7]["name"] = "Ouginak Wauwau owner"
        characters[8]["name"] = "Ouginak opponent"
        actors[0].direction = 0
        actors[1].direction = 3
        fight = Fight(
            78,
            actors,
            {
                (x, y, 0)
                for x in range(origin[0] - 6, origin[0] + 10)
                for y in range(origin[1] - 6, origin[1] + 7)
            },
            {0: {origin}, 1: {enemy_position}},
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.native_qi_snapshot = dict(
            x=origin[0] - 6,
            y=origin[1] - 6,
            width=16,
            height=13,
            cell_masks=[128] * (16 * 13),
        )
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters={},
            wp_resources=wp_resources,
            running_effects={identity: () for identity in characters},
            initial_effect_uid=1,
        )
        fight.ready(3)
        fight.ready(4)
        fight.native_obstacle_cells = frozenset()
        return characters, decks, fight

    def finish_current(self, characters, decks, fight, action_id):
        actor_id = fight.current.id
        preview, packets = prepare_server_turn_end(
            characters[7],
            {},
            fight,
            decks[7],
            actor_id=actor_id,
            action_id=action_id,
            rng=Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )
        actor = preview.actors[actor_id]
        if actor.controlled:
            preview.end_turn(actor.owner_id, actor_id, actor.turn_count)
        else:
            preview.end_server_turn(actor_id, preview.turn_id)
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        RuntimeMessages(preview).turn_started()
        return preview, packets

    def cast(self, characters, decks, fight, actor_id, uid, target, action_id):
        character = characters[7 if actor_id != 8 else 8]
        deck = decks[7 if actor_id != 8 else 8]
        owner_id = character["account_id"]
        line_of_sight = lambda source, destination, preview: authoritative_visible(
            character["map_id"],
            source,
            destination,
            preview,
            blocking_footprints={
                actor.id: footprint(actor.position, actor.physical_radius)
                for actor in preview.actors.values()
                if actor.hp > 0
            },
        )
        return prepare_server_spell(
            struct.pack(">qqiih", actor_id, uid, *target),
            character,
            {},
            fight,
            owner_id,
            deck,
            action_id=action_id,
            line_of_sight=line_of_sight,
            critical=False,
            rng=Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )

    def test_wauwau_book_control_death_retirement_and_reinvocation(self):
        characters, decks, fight = self.fixture()
        fight, _ = prepare_server_initialization(
            characters[7],
            {},
            fight,
            3,
            decks[7],
            action_id=1,
            rng=Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )
        fight, _ = prepare_server_initialization(
            characters[8],
            {},
            fight,
            4,
            decks[8],
            action_id=2,
            rng=Random(7),
            fight_start=True,
            player_characters=characters,
            deck_blobs=decks,
        )
        while fight.current.id != 7:
            fight, _ = self.finish_current(characters, decks, fight, 11)
        self.assertIn(6286, granted_spells(fight, 7))

        summon_cell = (-3, -18, 0)
        first = self.cast(characters, decks, fight, 7, 6286, summon_cell, 13)
        first_id = next(iter(set(first.fight.actors) - set(fight.actors)))
        wauwau = first.fight.actors[first_id]
        self.assertEqual(wauwau.native_summon_source["ref"], 4559)
        self.assertEqual(
            (wauwau.team, wauwau.controlled, wauwau.owner_id), (0, True, 3)
        )
        self.assertEqual(wauwau.native_controller_id, 7)
        self.assertEqual(
            {row["uid"] for row in wauwau.native_summon_action_book["actions"]},
            {6291, 6292, 6293, 6294},
        )
        self.assertEqual(set(actor_spellbook(wauwau).levels), {6291, 6292, 6293, 6294})
        registration = first.fight.native_summon_registrations[first_id]
        self.assertEqual(registration["controller_id"], 7)
        self.assertTrue(first.packets)

        # The caster retains its current turn; the exact fresh insertion gives
        # the registered summon the following controlled activation.
        fight = first.fight
        while fight.current.id != first_id:
            fight, _ = self.finish_current(characters, decks, fight, 15)
        controlled = self.cast(
            characters,
            decks,
            fight,
            first_id,
            6294,
            fight.actors[first_id].position,
            17,
        )
        self.assertEqual(controlled.plan["spell_id"], 6294)
        self.assertTrue(controlled.packets)

        fight = controlled.fight
        old_slot = fight.actors[first_id].native_obstacle_id
        killed = None
        action_id = 20
        for _ in range(4):
            while fight.current.id != 8:
                fight, _ = self.finish_current(characters, decks, fight, action_id)
                action_id += 1
            for spell in (6266, 6261):
                if fight.actors[first_id].hp <= 0:
                    break
                killed = self.cast(
                    characters,
                    decks,
                    fight,
                    8,
                    (8 << 32) | spell,
                    fight.actors[first_id].position,
                    action_id,
                )
                action_id += 1
                fight = killed.fight
            if fight.actors[first_id].hp <= 0:
                break
            fight, _ = self.finish_current(characters, decks, fight, action_id)
            action_id += 1
        self.assertIsNotNone(killed)
        self.assertEqual(fight.actors[first_id].hp, 0)
        self.assertIn(first_id, retired_summon_ids(fight))
        self.assertEqual(fight.actors[first_id].native_obstacle_id, -1)
        self.assertTrue(killed.packets)

        # Death releases the summon cell and its native QI slot, so the same
        # legal native cell can host a distinct fresh Wauwau on the next turn.
        last_summon_turn = fight.native_spell_usage["7"]["last"]["6286"]
        for action_id in range(22, 70):
            if (
                fight.current.id == 7
                and fight.native_table_turn - last_summon_turn >= 4
            ):
                break
            fight, _ = self.finish_current(characters, decks, fight, action_id)
        self.assertEqual(fight.current.id, 7)
        self.assertGreaterEqual(fight.native_table_turn - last_summon_turn, 4)
        second = self.cast(characters, decks, fight, 7, 6286, summon_cell, 70)
        second_ids = set(second.fight.actors) - set(fight.actors)
        self.assertEqual(len(second_ids), 1)
        second_id = next(iter(second_ids))
        self.assertNotEqual(second_id, first_id)
        self.assertEqual(second.fight.actors[second_id].position, summon_cell)
        self.assertIn(first_id, retired_summon_ids(second.fight))
        self.assertEqual(second.fight.actors[first_id].hp, 0)
        self.assertEqual(second.fight.actors[first_id].native_obstacle_id, -1)
        self.assertEqual(
            second.fight.actors[second_id].native_summon_source["ref"], 4559
        )
        self.assertEqual(second.fight.actors[second_id].native_obstacle_id, old_slot)
