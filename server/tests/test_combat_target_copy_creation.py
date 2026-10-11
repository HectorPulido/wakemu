"""Full eZq creation uses the selected player's source and the NPC controller."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_spell_level import NativeSpellBook
from wakfu_server.combat_summon import RegisteredSummonAuthority
from wakfu_server.combat_summon_creation import NativeSummonBuilder
from wakfu_server.combat_target_copy_handler import NativeTargetCopyHandler
from wakfu_server.combat_character_copy_metadata import (
    native_copy_characteristics,
    native_copy_book_document,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_summon_spellbook import actor_action_book
from wakfu_server.spells import owned_spell_records
from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT


class TargetCopyCreationTests(unittest.TestCase):
    def fixture(self):
        native_copy_characteristics.cache_clear()
        native_copy_book_document.cache_clear()
        self.addCleanup(native_copy_characteristics.cache_clear)
        self.addCleanup(native_copy_book_document.cache_clear)
        source = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "monster_target_copy2349_native.json"
            ).read_text()
        )
        original_load = native_catalog.load

        def load(path):
            if Path(path).name == "native-class-copy-characteristics.json":
                return source["copy_characteristics"]
            if Path(path).name == "native-class-copy-book-flags.json":
                return source["copy_book_flags"]
            if Path(path).name == "native-class-summon-abilities.json":
                return {"profiles": source["ability_profiles"]}
            return original_load(path)

        catalog_patch = patch.object(native_catalog, "load", side_effect=load)
        catalog_patch.start()
        self.addCleanup(catalog_patch.stop)
        metadata = native_copy_characteristics()
        character = dict(
            id=7,
            breed=9,
            level=1,
            name="Target source",
            appearance=dict(sex=0, clothIndex=0),
        )
        target = Actor(7, 0, (0, 0, 0), 100, 6, 3, 1, 1, owner_id=1, controlled=True)
        creator = Actor(-7, 1, (3, 3, 0), 100, 6, 3, 1, 1)
        cells = {(x, y, 0) for x in range(4) for y in range(4)}
        fight = Fight(
            994, [target, creator], cells, {0: {target.position}, 1: {creator.position}}
        )
        for actor in fight.actors.values():
            actor.physical_radius = 0
            actor.native_obstacle_id = 0 if actor.id == 7 else 1
            actor.native_carrier_id = actor.native_carried_actor_id = None
            actor.native_fight_property_counts = {}
        target.effect_stats = {
            int(k): row["current"]
            for k, row in metadata["fresh_characteristics"].items()
        }
        target.effect_maxima = {
            int(k): row["maximum"]
            for k, row in metadata["fresh_characteristics"].items()
        }
        target.effect_stats[1] = target.effect_maxima[1] = 100
        target.native_copy_appearance_source = dict(
            source_id=7, producer="owned.character.dS.don.v1", model=90, categories=()
        )
        records = owned_spell_records(character)
        book = NativeSpellBook(
            {reference: level for _, reference, level in records}, False
        )
        player_metadata = NativeActorAuthority(
            {},
            True,
            frozenset(),
            frozenset(),
            False,
            9,
            0,
            {},
            True,
            summon_root_id=7,
            native_real_level=1,
            native_instance_id=1134,
            native_controller_id=7,
            native_spellbook=book,
            native_actor_type=0,
            native_is_ehp=True,
        )
        npc_metadata = NativeActorAuthority(
            {},
            False,
            frozenset(),
            frozenset(),
            False,
            1,
            0,
            {},
            True,
            summon_root_id=-7,
            native_real_level=1,
            native_instance_id=1134,
            native_controller_id=-7,
            native_actor_type=1,
        )

        class Ordinary:
            characters = {7: character}
            monsters = {-7: dict(id=-7, ref=1)}

            def __call__(self, preview, actor):
                if preview.actors.get(actor.id) is not actor:
                    raise ValueError("Unknown fixture actor")
                return player_metadata if actor.id == 7 else npc_metadata

            def world_properties(self, preview, actor):
                return frozenset()

        authority = RegisteredSummonAuthority(Ordinary())
        fight.ready(1)
        definitions = native_catalog.load(DATA_ROOT / "spell-effect-trees.json")
        source_patch = patch(
            "wakfu_server.combat_target_copy_runtime_book._metadata",
            return_value=dict(
                definitions=definitions["spells"],
                effects=definitions["effects"],
                flags=source["copy_book_flags"]["spells"],
            ),
        )
        source_patch.start()
        self.addCleanup(source_patch.stop)
        profile_patch = patch(
            "wakfu_server.combat_summon_spellbook.profile_abilities",
            return_value=source["ability_profiles"],
        )
        profile_patch.start()
        self.addCleanup(profile_patch.stop)
        packets, allocated = [], []

        def allocate():
            uid = 901 + len(allocated)
            allocated.append(uid)
            return uid

        handler = NativeTargetCopyHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=allocate,
            context=lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            actor_authority=authority,
            container_level=lambda _: (True, 1),
            container=lambda _: (dict(container_type=None), None),
            casting_definitions=definitions["spells"],
            source_effects=definitions["effects"],
        )
        handler.builder = NativeSummonBuilder(
            authority,
            characteristics=source["characteristics"],
            properties=source["properties"],
            ability_profiles=source["ability_profiles"],
            initial_states=source["initial_states"]["profiles"],
        )
        return fight, handler, packets, records

    def test_selected_player_book_and_stats_are_created_under_npc_controller(self):
        fight, handler, packets, records = self.fixture()
        self.assertTrue(
            handler(
                dict(effect_class=994, parameters=[], target_masks=(None,) * 7),
                {},
                EffectInvocation(388786, 1, -7, 7, (1, 1, 0)),
            )
        )
        copy = fight.actors[902]
        self.assertEqual(copy.native_controller_id, -7)
        self.assertEqual(copy.team, fight.actors[-7].team)
        self.assertEqual(copy.native_summon_source["ref"], 2349)
        self.assertEqual(copy.native_summon_source["native_copy_source_actor_id"], 7)
        self.assertEqual(copy.native_copy_pa_source["native_copy_family"], 994)
        borrowed = {uid for uid, _, _ in records}
        actions = actor_action_book(copy)["actions"]
        self.assertTrue(actions)
        self.assertTrue({row["uid"] for row in actions} <= borrowed)
        self.assertNotIn(901, {row["uid"] for row in actions})
        self.assertEqual([opcode for opcode, _ in packets], [12613])

    def test_npc_target_cannot_borrow_the_other_players_connected_source(self):
        fight, handler, packets, _ = self.fixture()
        before = set(fight.actors)
        with self.assertRaisesRegex(ValueError, "connected class target-copy source"):
            handler(
                dict(effect_class=994, parameters=[], target_masks=(None,) * 7),
                {},
                EffectInvocation(388786, 1, 7, -7, (1, 1, 0)),
            )
        self.assertEqual(set(fight.actors), before)
        self.assertEqual(packets, [])
