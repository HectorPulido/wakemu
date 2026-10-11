import unittest
from unittest.mock import patch

from wakfu_server.characters import level_publication
from wakfu_server import wire


class LevelPublicationTests(unittest.TestCase):
    def test_real_level_roster_and_owned_spellbook_refresh_are_published_together(self):
        layout = {
            "sections": [{"name": name} for name in ("SPELL_INVENTORY", "SPELL_DECK")]
        }
        for level in (49, 50, 51):
            with self.subTest(level=level):
                character = {
                    "id": 3,
                    "account_id": 7,
                    "level": level,
                    "effective_level": 49,
                }
                with patch.dict(wire.ENTITY_LAYOUTS, {10: layout}), patch.object(
                    wire, "refresh_player", return_value=(15548, b"owned")
                ) as entity, patch.object(
                    wire, "character_list", return_value=b"roster"
                ) as roster:
                    packets = level_publication.refresh(
                        character,
                        [character],
                        entity_template=b"\x0a",
                        roster_template=b"template",
                    )
                self.assertEqual(packets, [(15548, b"owned"), (23548, b"roster")])
                entity.assert_called_once_with(b"\x0a", character)
                roster.assert_called_once_with(b"template", 7, [character])

    def test_stale_roster_and_foreign_characters_are_rejected(self):
        character = {"id": 3, "account_id": 7, "level": 51}
        layout = {
            "sections": [{"name": name} for name in ("SPELL_INVENTORY", "SPELL_DECK")]
        }
        for roster in (
            [],
            [dict(character, level=50)],
            [character, dict(character)],
            [character, {"id": 4, "account_id": 8, "level": 51}],
        ):
            with self.subTest(roster=roster), patch.dict(
                wire.ENTITY_LAYOUTS, {10: layout}
            ):
                with self.assertRaises(ValueError):
                    level_publication.refresh(
                        character, roster, entity_template=b"\x0a", roster_template=b""
                    )

    def test_world_format_without_spellbook_is_rejected(self):
        with self.assertRaises(ValueError):
            level_publication.refresh(
                {}, [], entity_template=b"\x0b", roster_template=b""
            )
