import unittest
import struct
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_character_copy_book import CopyBookAction
from wakfu_server.combat_character_copy_metadata import native_copy_book_flags
from wakfu_server.combat_character_copy_runtime_book import install_copied_action_book
from wakfu_server.combat_summon_spellbook import (
    actor_action_book,
    resolve_controlled_action,
)


class CopiedRuntimeBookTests(unittest.TestCase):
    def setUp(self):
        # Original scoped constructor2382 has no base abilities or initial states.
        self.profiles = patch(
            "wakfu_server.combat_summon_spellbook.profile_abilities",
            return_value={"2382": {"abilities": []}},
        )
        self.profiles.start()
        self.addCleanup(self.profiles.stop)
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
        self.actor = SimpleNamespace(
            id=42,
            effective_level=200,
            owner_id=3,
            controlled=True,
            native_controller_id=1,
            native_summon_source=dict(
                ref=2382,
                level=200,
                caster_id=1,
                controller_id=1,
                native_relation_source="big.new_bje.fdt_initial_registration",
                native_character_copy_source="eZw1002.faB.eHI.bPl",
                native_copy_source_actor_id=1,
                native_copy_effect_reference=413075,
            ),
        )
        install_copied_action_book(
            self.actor, (copied,), proof, effect_reference=413075
        )
        player = SimpleNamespace(id=1, owner_id=3, controlled=True)
        self.fight = SimpleNamespace(
            actors={1: player, 42: self.actor},
            native_summon_registrations={
                42: dict(
                    actor_id=42,
                    controller_id=1,
                    authority=dict(
                        is_summon=True,
                        is_player=False,
                        breed_id=2382,
                        native_real_level=200,
                        summon_root_id=1,
                        native_controller_id=1,
                        targeting=dict(dpr_id=1),
                    ),
                )
            },
        )

    def test_allocated_clone_uid_resolves_without_borrowing_source_or_raw_uid(self):
        self.assertEqual(
            resolve_controlled_action(self.fight, self.actor, 1, 3, 10001), (623, 200)
        )
        for uid in (623, (1 << 32) | 623, (42 << 32) | 623):
            with self.assertRaisesRegex(ValueError, "summon-owned action book"):
                resolve_controlled_action(self.fight, self.actor, 1, 3, uid)

    def test_mutated_copy_level_and_cross_actor_book_are_rejected(self):
        self.actor.native_summon_action_book["actions"][0]["level"] = 1
        with self.assertRaisesRegex(ValueError, "copied action-book population"):
            actor_action_book(self.actor)
        self.actor.native_summon_action_book["actions"][0]["level"] = 200
        self.actor.id = 43
        with self.assertRaisesRegex(ValueError, "copied-book source identity"):
            actor_action_book(self.actor)

    def test_removed_controller_remains_an_ownership_failure(self):
        del self.fight.actors[1]
        with self.assertRaisesRegex(ValueError, "no longer registered"):
            resolve_controlled_action(self.fight, self.actor, 1, 3, 10001)

    def test_owned_clone_and_player_inventory_uids_are_preserved_on_wire(self):
        from wakfu_server.combat_spells import cast_animation, cast_notification

        for actor_id, uid in ((42, 10001), (1, (1 << 32) | 623)):
            source = dict(id=actor_id)
            animation = cast_animation(
                1, 2, source, 623, (3, 4, 0), native_uid=uid, native_level=200
            )
            notification = cast_notification(
                1, 2, source, 623, (3, 4, 0), native_uid=uid, native_level=200
            )
            self.assertEqual(struct.unpack_from(">qih", animation, 20), (uid, 623, 200))
            self.assertEqual(
                struct.unpack_from(">qih", notification, 26), (uid, 623, 200)
            )
