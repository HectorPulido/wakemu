"""Noncombat owned content compiles and opens without combat-room creation."""

from copy import deepcopy
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import (
    dungeon_runtime,
    dungeon_runtime_config,
    generic_transports,
    owned_noncombat_context,
    owned_object_trials,
    owned_story_configuration,
)
from wakfu_server.achievements import storage
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.maps import dungeon_optional_rooms, quest_instance_configuration
from wakfu_server.maps import owned_story_mechanics, owned_story_exits


ROOT = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"


def trial_policy(map_id, source_pin):
    return dict(
        schema=owned_object_trials.SCHEMA,
        id="synthetic-noncombat-trials",
        map_id=map_id,
        maximum_members=1,
        native_sources=source_pin,
        steps=[],
        sources=[
            dict(
                id=90001,
                position=[0, 0, 0],
                descriptor_id=90002,
                action=0,
                duration_ms=0,
                payload_sha256="a" * 64,
                approaches=[[0, 0, 0]],
            )
        ],
        trials=[
            dict(
                id="synthetic-interaction",
                kind="ordered_objects",
                requires=[],
                sources=[90001],
                effects={"begin": [], "success": [], "failure": []},
            )
        ],
    )


class OwnedNoncombatContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (ROOT / "astrub-temple-887.instance.json").read_text()
        )
        story = json.loads((ROOT / "astrub-temple-887.json").read_text())
        cls.source_pin = story["native_sources"]
        cls.exploration = json.loads(
            (ROOT / "astrub-temple-887.exploration.json").read_text()
        )
        cls.geometry = published_geometry(887)
        cls.sources = {
            (row["map_id"], row["id"]): row for row in generic_transports._CATALOG
        }

    def compile(self):
        manifest = deepcopy(self.manifest)
        manifest.update(
            id="synthetic-noncombat-887",
            content_policy=owned_object_trials.SCHEMA,
            provenance="Synthetic test of native transport and walking integration.",
        )
        trials = trial_policy(self.geometry.map_id, self.source_pin)
        with patch.object(owned_story_mechanics, "sources", return_value={}):
            return owned_story_configuration.compile_object_trials(
                manifest,
                trials=trials,
                geometry=self.geometry,
                exploration=self.exploration,
                sources=self.sources,
            )

    def test_native_route_compiles_zero_rooms_and_skips_all_combat_progression(self):
        compiled = self.compile()
        topology = compiled["topology"]
        self.assertEqual(compiled["compiled_plan"]["rooms"], [])
        self.assertEqual(topology["rooms"], [])
        self.assertEqual(topology["policy"], owned_object_trials.SCHEMA)
        self.assertEqual(
            (
                compiled["route"]["entry_map_id"],
                compiled["route"]["entry_object_id"],
                compiled["route"]["destination_id"],
            ),
            (747, 23621, 4029),
        )
        self.assertEqual(
            {
                (row["source_id"], row["destination_id"])
                for row in topology["native_story_exits"]
            },
            {(23582, 2074), (23582, 2002), (23614, 2075), (23614, 2003)},
        )
        self.assertIs(
            owned_noncombat_context.selected(topology), topology["owned_object_trials"]
        )
        self.assertEqual(dungeon_optional_rooms.main_room_orders(topology), ())
        self.assertIs(
            quest_instance_configuration.reviewed_owned_policy(compiled),
            topology["owned_object_trials"],
        )
        route_map = quest_instance_configuration.merge_runtime_routes({}, [compiled])
        self.assertEqual(list(route_map), [compiled["route"]["key"]])

        db = Mock()
        groups = Mock()
        session = dict(instance_id=99)
        run = dict(instance_id=99)
        with patch.object(
            dungeon_runtime, "configuration_for_instance", return_value=(run, compiled)
        ), patch("wakfu_server.dungeon_progression.initialize_run") as initialize_run:
            self.assertIsNone(
                dungeon_runtime.initialize_instance(
                    db, session, groups=groups, geometry={}, store=Mock()
                )
            )
            self.assertIsNone(dungeon_runtime.ensure_current_room(db, groups, 99, {}))
        initialize_run.assert_not_called()
        db.execute.assert_not_called()
        groups.assert_not_called()

    def test_ordinary_empty_rooms_stay_invalid_and_owned_scope_requires_one_member(
        self,
    ):
        compiled = self.compile()
        topology = deepcopy(compiled["topology"])
        topology["policy"] = "owned-story-controller-v1"
        topology.pop("owned_object_trials")
        with self.assertRaisesRegex(ValueError, "encounter orders"):
            dungeon_runtime_config.prepare_configuration(
                compiled["compiled_plan"],
                topology,
                compiled["route"],
                version=compiled["version"],
                provenance="ordinary empty room rejection",
            )

        character = dict(id=17, account_id=9, instance_id=99, map_id=887, x=0, y=0, z=0)

        class DB:
            def __init__(self, members):
                self.members = members

            def execute(self, sql, _params):
                if "created_by_character_id" in sql:
                    return SimpleNamespace(
                        fetchone=lambda: dict(
                            context_route_key=compiled["route"]["key"],
                            context_policy_version=compiled["version"],
                            created_by_character_id=17,
                        )
                    )
                return SimpleNamespace(fetchall=lambda: self.members)

        store = SimpleNamespace(character=lambda *_: character)
        with patch.object(
            dungeon_runtime_config,
            "pinned_configuration",
            return_value=compiled,
        ):
            dungeon_runtime_config.require_monster_admission(compiled)
            selected, _ = owned_object_trials._scope(
                DB([dict(character_id=17)]), store, character
            )
            self.assertIs(selected, compiled["topology"]["owned_object_trials"])
            with self.assertRaisesRegex(ValueError, "one owner"):
                owned_object_trials._scope(
                    DB([dict(character_id=17), dict(character_id=18)]), store, character
                )
            nonempty = deepcopy(compiled)
            nonempty["compiled_plan"]["rooms"].append({"order": 1, "monsters": []})
            with self.assertRaisesRegex(ValueError, "cannot admit ordinary monsters"):
                dungeon_runtime_config.require_monster_admission(nonempty)

    def test_native_exit_uses_trial_scope_not_story_scope(self):
        compiled = self.compile()
        selected = compiled["topology"]["owned_object_trials"]
        binding = next(
            row
            for row in compiled["topology"]["native_story_exits"]
            if row["criterion"].startswith("!")
        )
        character = dict(
            id=17, account_id=9, instance_id=99, map_id=887, x=-18, y=-29, z=0
        )
        native_source = self.sources[(887, binding["source_id"])]
        body = struct.pack(
            ">qiBi", binding["source_id"], binding["destination_id"], 0, 2
        )
        with patch.object(
            dungeon_runtime, "configuration_for_instance", return_value=(None, compiled)
        ), patch.object(
            owned_object_trials, "_scope", return_value=(selected, character)
        ) as trial_scope, patch.object(
            owned_story_mechanics,
            "sources",
            side_effect=AssertionError("story scope used"),
        ), patch.object(
            owned_story_exits.generic_transports, "source", return_value=native_source
        ), patch.object(
            storage, "load_locked", return_value=dict(completed=[])
        ):
            authenticated = owned_story_exits.authenticate_exit(
                Mock(), Mock(), character, body, source_allowed=lambda *_: True
            )
        trial_scope.assert_called_once()
        self.assertIs(authenticated["controller"], selected)
        self.assertEqual(authenticated["completed_steps"], set())
        self.assertEqual(
            authenticated["destination"]["destination_id"], binding["destination_id"]
        )


if __name__ == "__main__":
    unittest.main()
