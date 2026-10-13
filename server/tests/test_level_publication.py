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


class CombatReturnLevelPublicationTests(unittest.TestCase):
    def test_only_loaded_owned_combat_heroes_refresh_without_activation(self):
        from wakfu_server.characters import hero_wire

        main = {"id": 3, "account_id": 7, "level": 14}
        hero = {"id": 4, "account_id": 7, "level": 11}
        unused = {"id": 5, "account_id": 7, "level": 1}
        with patch.object(
            level_publication, "refresh", return_value=[(15548, b"main")]
        ), patch.object(
            hero_wire, "refresh", return_value=(13046, b"hero")
        ) as refresh_hero, patch.object(
            hero_wire, "statistics", return_value=(15548, b"stats")
        ):
            packets = level_publication.combat_return(
                main,
                [main, hero, unused],
                participant_ids=(3, 4, 999),
                entity_template=b"template",
                roster_template=b"roster",
            )
        self.assertEqual(
            packets, [(15548, b"main"), (13046, b"hero"), (15548, b"stats")]
        )
        refresh_hero.assert_called_once_with(b"template", hero)

    def test_private_scene_hero_refresh_retains_selected_scene_projection(self):
        from wakfu_server.characters import hero_wire

        main = {
            "id": 3,
            "account_id": 7,
            "level": 14,
            "map_id": 1440,
            "instance_id": 123,
            "x": 2,
            "y": 3,
            "z": 0,
        }
        hero = {
            "id": 4,
            "account_id": 7,
            "level": 11,
            "map_id": 527,
            "instance_id": 0,
            "x": 99,
            "y": 99,
            "z": 0,
        }
        with patch.object(level_publication, "refresh", return_value=[]), patch.object(
            hero_wire, "refresh", return_value=(13046, b"hero")
        ) as refresh_hero, patch.object(
            hero_wire, "statistics", return_value=(15548, b"stats")
        ):
            level_publication.combat_return(
                main,
                [main, hero],
                participant_ids=(3, 4),
                entity_template=b"t",
                roster_template=b"r",
            )
        projected = refresh_hero.call_args.args[1]
        for key in ("map_id", "instance_id", "x", "y", "z"):
            self.assertEqual(projected[key], main[key])
        self.assertEqual(projected["id"], hero["id"])
        self.assertEqual(hero["map_id"], 527)
