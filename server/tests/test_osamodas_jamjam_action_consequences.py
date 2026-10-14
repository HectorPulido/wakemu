"""Real controlled Jamjam actions and two-owner aura lifecycle consequences."""
import os
import struct
import unittest
from random import Random
from unittest.mock import patch

from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.equipment_stats import effective_character, combat_resources
from wakfu_server.health import maximum
from wakfu_server.spells import encode_deck
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_summon_retirement import retired_summon_ids


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
@patch.dict(
    os.environ, {"WAKFU_NATIVE_GRANTED_CAST": "1", "WAKFU_NATIVE_AREA_CALLBACKS": "1"}
)
class JamjamActionConsequencesTests(unittest.TestCase):
    def fixture(self):
        characters, decks, actors, wp = {}, {}, [], {}
        for identity, account, team, breed, position in (
            (7, 3, 0, 2, (-4, -18, 0)),
            (8, 4, 0, 2, (-4, -16, 0)),
            (9, 5, 1, 15, (-4, -17, 0)),
        ):
            character = effective_character(
                dict(
                    id=identity,
                    account_id=account,
                    breed=breed,
                    level=200,
                    hp=maximum(breed, 200),
                    max_hp=maximum(breed, 200),
                    map_id=1134,
                    sex=0,
                    builds={},
                    inventory_items=[],
                )
            )
            character["sex"] = 0
            resources = combat_resources(character)
            characters[identity] = character
            decks[identity] = encode_deck(
                [7307, 7317, 7323] if breed == 2 else [6261, 6266],
                [7341, 7339] if breed == 2 else [],
            )
            actor = Actor(
                identity,
                team,
                position,
                character["hp"],
                resources["ap"],
                resources["mp"],
                resources["initiative"],
                200,
                account,
                True,
                max_hp=character["max_hp"],
            )
            actor.direction = 1
            actors.append(actor)
            wp[identity] = (resources["wp"], resources["wp"])
        fight = Fight(
            78,
            actors,
            {(x, y, 0) for x in range(-10, 5) for y in range(-24, -9)},
            {0: {actors[0].position, actors[1].position}, 1: {actors[2].position}},
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.native_qi_snapshot = dict(
            x=-10, y=-24, width=15, height=15, cell_masks=[128] * 225
        )
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters={},
            wp_resources=wp,
            running_effects={identity: () for identity in characters},
            initial_effect_uid=1,
        )
        for account in (3, 4, 5):
            fight.ready(account)
        fight.native_obstacle_cells = frozenset()
        for identity in (7, 8, 9):
            fight, _ = prepare_server_initialization(
                characters[identity],
                {},
                fight,
                characters[identity]["account_id"],
                decks[identity],
                action_id=identity,
                rng=Random(7),
                fight_start=(identity == 9),
                player_characters=characters,
                deck_blobs=decks,
            )
        return characters, decks, fight

    def finish(self, characters, decks, fight):
        from combat_audit_turns import advance_actual_turn

        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                characters[7],
                {},
                preview,
                decks[7],
                rng=Random(7),
                player_characters=characters,
                deck_blobs=decks,
                **boundary,
            ),
            turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                characters[7],
                {},
                preview,
                decks[7],
                rng=Random(7),
                area_callbacks=True,
                player_characters=characters,
                deck_blobs=decks,
                **boundary,
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {},
                decks[7],
                action_id=action_id,
                critical=False,
                rng=Random(7),
                player_characters=characters,
                deck_blobs=decks,
            )[0],
        )
        advance_actual_turn(runtime)
        return runtime.fight

    def turn(self, characters, decks, fight, identity):
        for _ in range(30):
            if fight.current.id == identity:
                return fight
            fight = self.finish(characters, decks, fight)
        self.fail(f"Actor {identity} did not receive its lawful turn")

    def cast(self, characters, decks, fight, identity, reference, target):
        actor = fight.actors[identity]
        controller = identity if identity in characters else actor.native_controller_id
        character = characters[controller]
        uid = (
            reference
            if identity not in characters or reference >= 7348
            else ((identity << 32) | reference)
        )
        original = snapshot(fight)
        result = prepare_server_spell(
            struct.pack(">qqiih", identity, uid, *target),
            character,
            {},
            fight,
            character["account_id"],
            decks[controller],
            action_id=200 + fight.turn_id,
            line_of_sight=lambda source, destination, preview: authoritative_visible(
                1134,
                source,
                destination,
                preview,
                blocking_footprints={
                    a.id: footprint(a.position, a.physical_radius)
                    for a in preview.actors.values()
                    if a.hp > 0
                },
            ),
            critical=False,
            rng=Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )
        self.assertEqual(snapshot(fight), original)
        return result.fight

    def summon(
        self, characters, decks, fight, owner=7, *, dragon=False, spend_owner_wp=False
    ):
        fight = self.turn(characters, decks, fight, owner)
        if dragon:
            fight = self.cast(
                characters, decks, fight, owner, 7349, fight.actors[owner].position
            )
        if spend_owner_wp:
            fight = self.cast(
                characters, decks, fight, owner, 7323, fight.actors[owner].position
            )
        x, y, z = fight.actors[owner].position
        old = set(fight.actors)
        fight = self.cast(characters, decks, fight, owner, 7350, (x + 1, y, z))
        fresh = set(fight.actors) - old
        self.assertEqual(len(fresh), 1)
        identity = fresh.pop()
        self.assertEqual(fight.actors[identity].native_summon_source["ref"], 1620)
        self.assertEqual(fight.actors[identity].native_controller_id, owner)
        for _ in range(30):
            if fight.current.id == identity:
                return fight, identity
            fight = self.finish(characters, decks, fight)
        self.fail("Fresh Jamjam never received its actual controlled turn")

    def move(self, characters, decks, fight, identity, path):
        actor = fight.actors[identity]
        controller = identity if identity in characters else actor.native_controller_id
        origin = actor.position
        fight.move(actor.owner_id, identity, path)
        preview, _ = prepare_area_movement(
            characters[controller],
            {},
            fight,
            decks[controller],
            actor_id=identity,
            action_id=300 + fight.turn_id,
            path=path,
            origin=origin,
            rng=Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )
        return preview

    def test_astral_exchange_swaps_owner_and_jamjam_and_spends_one_wp(self):
        characters, decks, fight = self.fixture()
        fight, jamjam = self.summon(characters, decks, fight)
        owner_cell, jam_cell = fight.actors[7].position, fight.actors[jamjam].position
        wp = fight.actors[jamjam].effect_stats[4]
        result = self.cast(characters, decks, fight, jamjam, 7351, owner_cell)
        self.assertEqual(result.actors[7].position, jam_cell)
        self.assertEqual(result.actors[jamjam].position, owner_cell)
        self.assertEqual(result.actors[jamjam].effect_stats[4], wp - 1)
        self.assertEqual(result.actors[8].position, fight.actors[8].position)

    def test_lunar_applies_real_owner_state_and_owned_aura(self):
        characters, decks, fight = self.fixture()
        fight, jamjam = self.summon(characters, decks, fight)
        result = self.cast(
            characters, decks, fight, jamjam, 7352, fight.actors[7].position
        )
        lunar = [
            entry
            for entry in result.actors[7].state_ledger.entries
            if entry.reference == 7151
        ]
        self.assertEqual(len(lunar), 1)
        self.assertEqual(lunar[0].level, 1)
        self.assertFalse(
            any(e.reference == 7152 for e in result.actors[7].state_ledger.entries)
        )
        self.assertTrue(
            any(row["reference"] == 1689 for row in result.native_effect_areas.values())
        )
        self.assertFalse(
            any(e.reference == 7151 for e in result.actors[8].state_ledger.entries)
        )

    def test_solar_applies_real_owner_state_at_native_minimum_range(self):
        characters, decks, fight = self.fixture()
        fight, jamjam = self.summon(characters, decks, fight)
        fight = self.move(
            characters, decks, fight, jamjam, [(-2, -18, 0), (-1, -18, 0)]
        )
        wp = fight.actors[jamjam].effect_stats[4]
        result = self.cast(
            characters, decks, fight, jamjam, 7353, fight.actors[7].position
        )
        solar = [
            entry
            for entry in result.actors[7].state_ledger.entries
            if entry.reference == 7152
        ]
        self.assertEqual(len(solar), 1)
        self.assertEqual(solar[0].level, 1)
        self.assertEqual(result.actors[jamjam].effect_stats[4], wp - 1)
        refs = {row["reference"] for row in result.native_effect_areas.values()}
        self.assertTrue({1690, 1692} <= refs)

    def test_motivation_adds_two_actual_owner_mp_maximum_and_current(self):
        characters, decks, fight = self.fixture()
        fight, jamjam = self.summon(characters, decks, fight)
        before_current = fight.actors[7].mp
        before_maximum = fight.actors[7].max_mp
        enemy_current = fight.actors[9].mp
        enemy_maximum = fight.actors[9].max_mp
        result = self.cast(
            characters, decks, fight, jamjam, 7354, fight.actors[7].position
        )
        self.assertEqual(result.actors[7].max_mp, before_maximum + 2)
        self.assertEqual(result.actors[7].mp, before_current + 2)
        self.assertEqual(result.actors[9].mp, enemy_current)
        self.assertEqual(result.actors[9].max_mp, enemy_maximum)

    def test_nova_restores_owner_wp_and_retires_jamjam_without_orphan_turn(self):
        characters, decks, fight = self.fixture()
        fight, jamjam = self.summon(characters, decks, fight, spend_owner_wp=True)
        before = fight.actors[7].effect_stats[4]
        self.assertLess(before, fight.actors[7].effect_maxima[4])
        result = self.cast(
            characters, decks, fight, jamjam, 7355, fight.actors[7].position
        )
        self.assertEqual(
            result.actors[7].effect_stats[4],
            min(before + 3, result.actors[7].effect_maxima[4]),
        )
        self.assertIn(jamjam, retired_summon_ids(result))
        self.assertEqual(result.actors[jamjam].native_obstacle_id, -1)
        self.assertNotEqual(result.current.id, jamjam)
