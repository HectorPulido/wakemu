import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_spell_level import NativeSpellBook
from wakfu_server.combat_spell_grant_book import (
    merged_grant_book,
    register_raw_removal,
    grant_record,
)


class SpellGrantBookTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            id=1, owner_id=7, controlled=True, hp=10, effective_level=30
        )
        self.fight = SimpleNamespace(
            actors={1: self.actor},
            current=self.actor,
            phase="active",
            native_spell_grants={1: {100: dict(uid=100, reference=100, level=20)}},
        )

    def test_player_grants_do_not_create_progression_levels_or_bypass_cap(self):
        book = NativeSpellBook({99: 30}, True, {99: 30}, 10)
        merged = merged_grant_book(self.fight, 1, book)
        self.assertEqual(merged.levels, {99: 30, 100: 20})
        self.assertEqual(merged.level(99), 10)
        self.assertEqual(merged.level(100), -1)
        self.assertEqual(book.levels, {99: 30})

    def test_raw_summon_uid_collision_retains_existing_level_and_removal(self):
        book = NativeSpellBook({100: 6, 101: 10}, False)
        self.assertEqual(merged_grant_book(self.fight, 1, book).level(100), 6)
        self.fight.native_spell_grants[1].clear()
        register_raw_removal(self.fight, 1, 100)
        merged = merged_grant_book(self.fight, 1, book)
        self.assertEqual(merged.level(100), 0)
        self.assertEqual(merged.level(101), 10)
        self.assertEqual(book.level(100), 6)
        self.fight.native_spell_grants[1][100] = dict(uid=100, reference=100, level=20)
        self.assertEqual(merged_grant_book(self.fight, 1, book).level(100), 20)

    def test_removed_raw_uid_does_not_remove_player_packed_object(self):
        register_raw_removal(self.fight, 1, 99)
        book = NativeSpellBook({99: 30}, True, {99: 30})
        self.assertEqual(merged_grant_book(self.fight, 1, book).level(99), 30)

    def test_valid_registered_grant_cast_does_not_require_feature_flag_or_player_deck(
        self,
    ):
        from wakfu_server.combat_cast import resolve_owned_spell_action

        request = dict(actor_id=1, spell_uid=100)
        with patch.dict(os.environ, {"WAKFU_NATIVE_GRANTED_CAST": "0"}), patch(
            "wakfu_server.combat_cast.validate_deck",
            side_effect=AssertionError("Borrowed deck"),
        ):
            actor, reference, level = resolve_owned_spell_action(
                request, dict(id=1), self.fight, 7, b""
            )
        self.assertIs(actor, self.actor)
        self.assertEqual((reference, level), (100, 20))
        self.fight.native_spell_grants[1].clear()
        with self.assertRaisesRegex(ValueError, "expired grant"):
            resolve_owned_spell_action(request, dict(id=1), self.fight, 7, b"")

    def test_grant_never_bypasses_current_actor_owner_or_life(self):
        from wakfu_server.combat_cast import resolve_owned_spell_action

        request = dict(actor_id=1, spell_uid=100)
        for key, value in (("owner_id", 8), ("controlled", False), ("hp", 0)):
            original = getattr(self.actor, key)
            setattr(self.actor, key, value)
            with self.assertRaisesRegex(ValueError, "owned active actor"):
                resolve_owned_spell_action(request, dict(id=1), self.fight, 7, b"")
            setattr(self.actor, key, original)

    def test_malformed_registry_is_rejected(self):
        self.fight.native_spell_grants[1][100]["level"] = True
        with self.assertRaisesRegex(ValueError, "owned native"):
            grant_record(self.fight, 1, 100)

    def test_proved_null_book_does_not_become_an_invented_book(self):
        with self.assertRaisesRegex(ValueError, "no owning spellbook"):
            merged_grant_book(self.fight, 1, NativeSpellBook(None, False))
        self.fight.native_spell_grants[1].clear()
        book = NativeSpellBook(None, False)
        self.assertIs(merged_grant_book(self.fight, 1, book), book)


if __name__ == "__main__":
    unittest.main()
