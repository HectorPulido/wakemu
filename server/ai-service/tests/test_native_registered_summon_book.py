"""Registered native books retain their own level and authority in AI advice."""
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
import unittest

from wakfu_ai.native.native_oracle import NativeOracle


class NativeRegisteredSummonBookTests(unittest.TestCase):
    def fixture(self, reference=1361, level=34, *, profiles=None):
        from wakfu_server.combat_summon_spellbook import fresh_action_book

        source = dict(
            ref=reference,
            level=level,
            caster_id=-1,
            controller_id=-1,
            direction=3,
            native_relation_source="big.new_bje.fdt_initial_registration",
        )
        actor = SimpleNamespace(
            id=7,
            hp=100,
            effective_level=level,
            team=1,
            position=(0, 0, 0),
            native_summon_source=source,
            native_summon_action_book=fresh_action_book(
                reference, level, profiles=profiles
            ),
        )
        registration = dict(
            actor_id=7,
            caster_id=-1,
            controller_id=-1,
            authority=dict(
                is_summon=True,
                is_player=False,
                breed_id=reference,
                native_real_level=level,
                native_instance_id=1134,
            ),
        )
        fight = SimpleNamespace(
            current=actor,
            actors={7: actor},
            native_summon_registrations={7: registration},
        )
        oracle = NativeOracle.__new__(NativeOracle)
        oracle.characters, oracle.monsters, oracle.companions = {}, {}, {}
        return oracle, fight, actor

    def test_registered_book_accepts_native_birth_level_and_preserves_grants(self):
        oracle, fight, actor = self.fixture()
        self.assertEqual(oracle.owned_spells(fight), {3636: 34})
        fight.native_spell_grants = {actor.id: {3637: dict(uid=3637, level=2)}}
        self.assertEqual(oracle.owned_spells(fight), {3636: 34, 3637: 2})
        fight.native_spell_grants[actor.id][3637]["uid"] = 99
        with self.assertRaisesRegex(ValueError, "temporary spell UID"):
            oracle.owned_spells(fight)

    def test_changed_registration_or_native_book_is_rejected(self):
        oracle, fight, actor = self.fixture()
        fight.native_summon_registrations[actor.id]["authority"][
            "native_real_level"
        ] = 35
        with self.assertRaisesRegex(ValueError, "registered summon authority"):
            oracle.owned_spells(fight)
        fight.native_summon_registrations[actor.id]["authority"][
            "native_real_level"
        ] = 34
        actor.native_summon_action_book = deepcopy(actor.native_summon_action_book)
        actor.native_summon_action_book["actions"][0]["level"] = 35
        with self.assertRaisesRegex(ValueError, "summon action book"):
            oracle.owned_spells(fight)

    def test_fresh_crow_successors_keep_constructor_books(self):
        for reference, expected in (
            (1989, {7505: 100, 7506: 100, 7507: 100, 7509: 100, 7510: 100}),
            (5356, {7499: 110}),
        ):
            with self.subTest(reference=reference):
                oracle, fight, actor = self.fixture(reference, 110)
                self.assertEqual(oracle.owned_spells(fight), expected)

    def test_captured_book_retains_its_source_and_controller_authority(self):
        from wakfu_server.combat_captured_profiles import native_captured_profiles

        oracle, fight, actor = self.fixture(
            1152, 110, profiles=native_captured_profiles()
        )
        actor.native_summon_source[
            "native_symbiot_source"
        ] = "eZr324.after_common_factory_and_fan.lE_true"
        self.assertEqual(
            oracle.owned_spells(fight),
            {
                1522: 110,
                3558: 110,
                1525: 110,
                7365: 110,
                7366: 110,
                7367: 110,
            },
        )
        fight.native_summon_registrations[actor.id]["controller_id"] = 99
        with self.assertRaisesRegex(ValueError, "registered summon authority"):
            oracle.owned_spells(fight)

    def test_copied_book_uses_owned_clone_and_rejects_changed_population(self):
        from wakfu_server.combat_character_copy_book import CopyBookAction
        from wakfu_server.combat_character_copy_metadata import native_copy_book_flags
        from wakfu_server.combat_character_copy_runtime_book import (
            install_copied_action_book,
        )

        oracle, fight, actor = self.fixture(2382, 200)
        actor.native_summon_source.update(
            native_character_copy_source="eZw1002.faB.eHI.bPl",
            native_copy_source_actor_id=1,
            native_copy_effect_reference=413075,
        )
        flags = native_copy_book_flags()["623"]
        original = CopyBookAction(
            (1 << 32) | 623,
            623,
            200,
            flags["native_elO"],
            flags["native_elemental_copy"],
            flags["native_neutral_copy"],
        )
        copied = CopyBookAction(
            10001, 623, 200, original.special, original.elemental, original.neutral
        )
        proof = dict(
            producer="server.current_owned_inventory.faC.eZx",
            source_actor_id=1,
            source_actions=[asdict(original)],
            copied_actions=[asdict(copied)],
            allocated_clone_uids=[10001],
            available_references=[623],
            selector_cap=-1,
            actor_cap=200,
            minimum=0,
            maximum=200,
        )
        install_copied_action_book(actor, (copied,), proof, effect_reference=413075)
        self.assertEqual(oracle.owned_spells(fight), {623: 200})
        self.assertEqual(actor.native_summon_action_book["actions"][0]["uid"], 10001)
        actor.native_summon_action_book["actions"][0]["uid"] = 623
        with self.assertRaisesRegex(ValueError, "copied action-book population"):
            oracle.owned_spells(fight)

    def test_ordinary_creature_still_delegates_to_its_ordinary_book(self):
        from unittest.mock import patch

        oracle, fight, actor = self.fixture()
        fight.native_summon_registrations = {}
        oracle.monsters = {actor.id: dict(id=actor.id, ref=1361, level=34)}
        with patch(
            "wakfu_server.monsters.native_abilities",
            return_value=[
                dict(spell_id=3636, spell_level=34),
            ],
        ) as ordinary:
            self.assertEqual(oracle.owned_spells(fight), {3636: 34})
        ordinary.assert_called_once_with(1361, 34)


if __name__ == "__main__":
    unittest.main()
