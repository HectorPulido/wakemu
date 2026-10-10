"""Preview copies share immutable assets and isolate owned authority sources."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat.combat_ordinary_authority import (
    OrdinaryActorAuthority,
    _immutable_property_catalog,
    native_property_catalog,
)
from wakfu_server.combat.combat_summon import RegisteredSummonAuthority


class PropertyCatalogCopyTests(unittest.TestCase):
    def tearDown(self):
        native_property_catalog.cache_clear()
        _immutable_property_catalog.cache_clear()

    def authority(self, **options):
        return OrdinaryActorAuthority(
            characters={1: {"id": 1, "inventory": [7]}},
            monsters={},
            decks={1: [2]},
            excluded_decks={1: []},
            **options
        )

    def test_asset_catalog_is_shared_but_actor_and_deck_sources_are_isolated(self):
        source = {"player": {"fight_properties": [1]}, "npc": {}}
        native_property_catalog.cache_clear()
        _immutable_property_catalog.cache_clear()
        with patch(
            "wakfu_server.combat.combat_ordinary_authority.protocol_catalog.load",
            return_value=source,
        ):
            authority = self.authority()
            self.assertIs(native_property_catalog(), source)
            self.assertEqual(
                native_property_catalog()["player"]["fight_properties"], [1]
            )
        cloned = copy.deepcopy(authority)
        self.assertEqual(
            json.dumps(cloned.catalog, sort_keys=True),
            json.dumps(source, sort_keys=True),
        )
        self.assertIs(cloned.catalog, authority.catalog)
        with self.assertRaises(TypeError):
            cloned.catalog["player"]["changed"] = True
        self.assertEqual(cloned.catalog["player"]["fight_properties"], (1,))
        cloned.characters[1]["inventory"].append(8)
        cloned.decks[1].append(3)
        self.assertEqual(authority.characters[1]["inventory"], [7])
        self.assertEqual(authority.decks[1], [2])

        fight = SimpleNamespace(
            native_rail_movement_authority=RegisteredSummonAuthority(authority),
            actors={1: {"hp": 100}},
        )
        preview = copy.deepcopy(fight)
        copied_authority = preview.native_rail_movement_authority.ordinary
        self.assertIs(copied_authority.catalog, authority.catalog)
        self.assertIsNot(copied_authority, authority)
        copied_authority.characters[1]["inventory"].append(9)
        preview.actors[1]["hp"] = 1
        self.assertEqual(authority.characters[1]["inventory"], [7])
        self.assertEqual(fight.actors[1]["hp"], 100)

    def test_custom_mutable_catalog_remains_isolated(self):
        authority = self.authority(catalog={"player": {"fight_properties": [1]}})
        cloned = copy.deepcopy(authority)
        cloned.catalog["player"]["fight_properties"].append(2)
        self.assertEqual(authority.catalog["player"]["fight_properties"], [1])


if __name__ == "__main__":
    unittest.main()
