"""Challenge profile admission uses indexed native authority without combat catalogs."""
import sys
import types
import unittest
from unittest.mock import Mock, patch

import wakfu_server
from wakfu_server.objectives.challenges_profiles import validate_profile


def module(name, **attributes):
    result = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(result, key, value)
    return result


class ChallengeProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "key": "fixture-weekly-profile",
            "title": "Fixture weekly profile",
            "enabled": True,
            "min_level": 1,
            "max_level": 20,
            "map_id": 1086,
            "anchor": [-11, -17, 0],
            "roster": [{"ref_id": 1, "level": 10, "count": 1}],
            "source_route_key": "fixture-native-route",
        }
        self.record = Mock(return_value={"1": {"min_level": 1, "max_level": 20}})
        self.fake_modules = {
            "wakfu_server.monsters": module(
                "wakfu_server.monsters",
                reference=Mock(return_value={"min_level": 1, "max_level": 20}),
                statistics=Mock(return_value={}),
            ),
            "wakfu_server.monster_minigame_policy": module(
                "wakfu_server.monster_minigame_policy", require_ordinary_spawn=Mock()
            ),
            "wakfu_server.paths": module(
                "wakfu_server.paths", DATA_ROOT=__import__("pathlib").Path("/native")
            ),
            "wakfu_server.combat_terrain": module(
                "wakfu_server.combat_terrain",
                map_geometry=Mock(return_value={"cells": [], "edges": []}),
            ),
            "wakfu_server.dungeon_encounters": module(
                "wakfu_server.dungeon_encounters",
                enemy_formation=Mock(return_value=[(-11, -17, 0)]),
            ),
        }
        self.native = module("wakfu_server.native_catalog", record=self.record)

    def invoke(self):
        with patch.object(
            wakfu_server, "native_catalog", self.native, create=True
        ), patch.dict(sys.modules, self.fake_modules):
            return validate_profile(self.profile)

    def test_profile_uses_indexed_enabled_monster_authority_without_loading_combat_effects(
        self,
    ):
        heavy = "wakfu_server.combat.combat_npc_attack"
        was_loaded = heavy in sys.modules
        self.assertEqual(self.invoke(), self.profile)
        self.record.assert_called_once_with(
            __import__("pathlib").Path("/native/native-npc-spell-effect-trees.json"),
            "activation_policy",
            "enabled_monsters",
        )
        self.assertEqual(heavy in sys.modules, was_loaded)

    def test_profile_rejects_monster_missing_native_activation_authority(self):
        self.record.return_value = {}
        with self.assertRaisesRegex(ValueError, "not enabled at its native level"):
            self.invoke()


if __name__ == "__main__":
    unittest.main()
