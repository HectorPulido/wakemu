import unittest
from unittest.mock import Mock
from wakfu_server.characters import starter_decks
from wakfu_server import builds, spells, wire


class StarterDeckTests(unittest.TestCase):
    def character(self, level=14):
        return {"id": 46, "account_id": 23, "breed": 8, "level": level, "builds": {}}

    def test_virtual_default_materializes_current_six_without_resetting_loadout(self):
        db = Mock()
        character = self.character()
        starter_decks.initialize(db, character)
        query, args = db.execute.call_args.args
        self.assertIn("ON CONFLICT(character_id,build_index) DO NOTHING", query)
        self.assertEqual(args[3], spells.default_deck(character))
        self.assertEqual(len(spells.validate_deck(args[3], 8, 14)["active"]), 6)
        self.assertEqual((args[2], args[4]), (b"", b""))

    def test_leveling_unlocks_library_without_replacing_materialized_deck(self):
        character = self.character(8)
        deck = spells.default_deck(character)
        sheet = next(
            value
            for tag, value in wire.proto_fields(builds.build_set(character, b""))
            if tag == 18
        )
        character.update(
            level=14, builds={0: {"sheet": sheet.hex(), "deck": deck.hex()}}
        )
        db = Mock()
        starter_decks.initialize(db, character)
        db.execute.assert_not_called()
        self.assertIn(
            4782, {record[1] for record in spells.owned_spell_records(character)}
        )
        self.assertNotIn(4782, spells.validate_deck(deck, 8, 14)["active"])

    def test_existing_empty_deck_updates_only_deck_at_sheet_level(self):
        character = self.character()
        sheet = b"".join(
            wire.proto_field(tag, value)
            for tag, value in ((8, 0), (18, b"Owned"), (24, 8), (56, 7))
        )
        character["builds"] = {
            0: {
                "sheet": sheet.hex(),
                "deck": "",
                "equipment": "1234",
                "aptitudes": "5678",
            }
        }
        db = Mock()
        starter_decks.initialize(db, character)
        query, args = db.execute.call_args.args
        self.assertIn("UPDATE character_builds SET deck=%s", query)
        self.assertIn("octet_length(deck)=0", query)
        self.assertEqual(
            args, (spells.default_deck(dict(character, effective_level=8)), 46, 0)
        )
