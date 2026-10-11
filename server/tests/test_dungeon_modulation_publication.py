"""Boundary profile publication must install registries before selecting a build."""
import struct
import unittest
from unittest.mock import patch

from wakfu_server.characters import dungeon_modulation_publication as publication


class DungeonModulationPublicationTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(
            id=7,
            account_id=9,
            level=200,
            active_build_index=127,
            builds={127: {}},
            dungeon_modulation={"effective_level": 50},
        )
        self.template = b"\x0aowned"
        self.original = b"\0\0" + struct.pack(">I", len(self.template)) + self.template
        self.fixture = lambda opcode: self.original if opcode == 12666 else b"sheets"

    def test_registry_precedes_selection_and_uses_same_authoritative_profile(self):
        with patch.object(
            publication.wire, "adapt", return_value=b"fresh-owned"
        ) as owned, patch.object(
            publication.wire, "attribute_sheets", return_value=b"fresh-sheets"
        ) as sheets, patch.object(
            publication.hero_wire, "refresh", return_value=(13046, b"fresh-public")
        ) as appearance, patch(
            "wakfu_server.combat_lifecycle.outside_progression",
            return_value=(12436, b"fresh-health"),
        ):
            result = publication.packets(self.character, self.fixture)
        self.assertEqual(
            [opcode for opcode, _ in result], [12666, 12393, 13811, 13046, 12436]
        )
        self.assertEqual(result[2][1], struct.pack(">qb", 7, 127))
        owned.assert_called_once_with(12666, self.original, 9, self.character)
        sheets.assert_called_once_with(b"sheets", (self.character,))
        appearance.assert_called_once_with(self.template, self.character)

    def test_restored_owned_selection_uses_identical_publication_path(self):
        self.character.update(active_build_index=0, builds={}, dungeon_modulation=None)
        with patch.object(
            publication.wire, "adapt", return_value=b"owned"
        ), patch.object(
            publication.wire, "attribute_sheets", return_value=b"sheets"
        ), patch.object(
            publication.hero_wire, "refresh", return_value=(13046, b"public")
        ), patch(
            "wakfu_server.combat_lifecycle.outside_progression",
            return_value=(12436, b"hp"),
        ):
            result = publication.packets(self.character, self.fixture)
        self.assertEqual(result[2][1], struct.pack(">qb", 7, 0))

    def test_foreign_roster_and_missing_selected_build_fail_before_encoding(self):
        with patch.object(publication.wire, "adapt") as encode:
            with self.assertRaisesRegex(ValueError, "foreign"):
                publication.packets(
                    self.character,
                    self.fixture,
                    owned_characters=[self.character, dict(id=8, account_id=10)],
                )
            self.character["active_build_index"] = 126
            with self.assertRaisesRegex(ValueError, "selection"):
                publication.packets(self.character, self.fixture)
        encode.assert_not_called()

    def test_missing_fixture_or_wrong_native_entity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "fixtures"):
            publication.packets(self.character, None)
        with self.assertRaisesRegex(ValueError, "format10"):
            publication.packets(self.character, lambda opcode: b"\0\0\0\0\0\1\x0b")

    def test_company_role_comes_from_durable_membership_after_switch(self):
        from unittest.mock import Mock

        db = Mock()
        db.execute.return_value.fetchone.side_effect = [dict(leader_id=7)]
        self.assertFalse(publication.owned_hero_role(db, 9, 7))
        db.execute.return_value.fetchone.side_effect = [dict(leader_id=8), (1,)]
        self.assertTrue(publication.owned_hero_role(db, 9, 7))
        db.execute.return_value.fetchone.side_effect = [dict(leader_id=8), None]
        with self.assertRaisesRegex(ValueError, "company"):
            publication.owned_hero_role(db, 9, 7)

    def test_owned_hero_uses_activation_not_main_registration(self):
        with patch.object(
            publication.hero_wire, "activate", return_value=(12093, b"hero")
        ) as activate, patch.object(publication.wire, "adapt") as main, patch.object(
            publication.wire, "attribute_sheets", return_value=b"sheets"
        ), patch.object(
            publication.hero_wire, "refresh", return_value=(13046, b"public")
        ), patch(
            "wakfu_server.combat_lifecycle.outside_progression",
            return_value=(12436, b"hp"),
        ):
            result = publication.packets(self.character, self.fixture, owned_hero=True)
        self.assertEqual(result[0], (12093, b"hero"))
        activate.assert_called_once_with(self.template, self.character)
        main.assert_not_called()
