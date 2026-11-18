import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight

ROOT = Path(__file__).parents[1]
PROFILE_DIR = ROOT / "wakfu_server" / "maps" / "owned_story_profiles"


class CombatSceneBallResourcesTests(unittest.TestCase):
    def test_original_form_projects_only_battle_resource_pool_after_receipt(self):
        from wakfu_server.combat_actor_snapshot import (
            native_actor_catalog,
            native_npc_creation_values,
        )
        from wakfu_server.combat_morph_spellbook import install_morph_book
        from wakfu_server.combat_scene_ball_goals import declaration
        from wakfu_server.combat_scene_ball_resources import (
            project,
            validate_projection,
        )

        encounters = json.loads(
            (PROFILE_DIR / "wild-estate-bworkball-719-encounters.json").read_text()
        )
        descriptor = encounters["rooms"][0]["encounter_scene"]
        cells = [(-9, -4, 0), (-8, -4, 0), (-7, -4, 0)]
        scope = dict(
            map_id=719,
            instance_id=7001,
            group_id=7002,
            room_order=1,
            policy_version=1,
            route_key="bworkball-room-1",
            evidence_hashes={},
            actor_bindings=[],
        )
        scene = dict(
            schema_version=1, descriptor=descriptor, scope=scope, room_cells=cells
        )
        from hashlib import sha256

        scene["sha256"] = sha256(
            json.dumps(
                scene, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        selected = declaration(descriptor)

        catalog = native_actor_catalog()
        profile = catalog["npc_profiles"]["2784"]
        level = profile["base_level"]
        native = native_npc_creation_values(2784, level, catalog=catalog)
        values = {key: row["current"] for key, row in native.items()}
        actor = Actor(
            2338,
            0,
            (-9, -4, 0),
            values[1],
            values[2],
            values[3],
            10,
            50,
            owner_id=77,
            controlled=True,
        )
        actor.effect_stats = values
        actor.effect_maxima = {key: row["maximum"] for key, row in native.items()}
        actor.effect_minima = {key: row["minimum"] for key, row in native.items()}
        actor.effect_base_maxima = dict(actor.effect_maxima)
        actor.effect_base_minima = dict(actor.effect_minima)
        actor.effect_percentages = {key: 0 for key in native}
        actor.effect_frozen = frozenset(
            key for key, row in native.items() if row["frozen"]
        )
        fight = Fight(
            7003,
            [actor, Actor(-7004, 1, (-8, -4, 0), 100, 6, 3, 5, 50)],
            set(cells),
            {0: {actor.position}, 1: {(-8, -4, 0)}},
        )
        fight.phase = "active"
        fight.turn_id = 1
        fight.native_class_initializations = {actor.id: {"breed": 11}}
        programs = descriptor["controlled_state_programs"]
        fight.native_controlled_scene_state_receipt = dict(
            scene_sha256=scene["sha256"], actor_id=actor.id, programs=programs
        )

        profile_path = Path(
            ".runtime/quest-archetypes/line9-native/bworkball-native/native-profiles.json"
        )
        morph_profile = json.loads(profile_path.read_text())["profiles"]["2784"]
        install_morph_book(fight, actor, morph_profile, own_level=True, uid=105570)
        fight.native_encounter_scene = scene
        with patch(
            "wakfu_server.combat_scene_ball_goals._scene",
            return_value=(scene, selected),
        ):
            before_stats = dict(actor.effect_stats)
            fight.native_controlled_scene_state_receipt = dict(
                scene_sha256="0" * 64, actor_id=actor.id, programs=programs
            )
            with self.assertRaises(ValueError):
                project(fight, catalog=catalog)
            fight.native_controlled_scene_state_receipt = dict(
                scene_sha256=scene["sha256"], actor_id=actor.id, programs=programs
            )
            self.assertTrue(project(fight, catalog=catalog))
            receipt = validate_projection(fight, catalog=catalog)
            self.assertEqual((receipt["owner_id"], receipt["reference"]), (2338, 2784))
            self.assertEqual(
                actor.effect_stats[1], receipt["resources"]["1"]["current"]
            )
            self.assertEqual(
                actor.effect_stats[2], receipt["resources"]["2"]["current"]
            )
            self.assertEqual(
                actor.effect_stats[3], receipt["resources"]["3"]["current"]
            )
            self.assertEqual(
                actor.effect_stats[4], receipt["resources"]["4"]["current"]
            )
            self.assertEqual(
                {
                    key: value
                    for key, value in actor.effect_stats.items()
                    if key not in (1, 2, 3, 4)
                },
                {
                    key: value
                    for key, value in before_stats.items()
                    if key not in (1, 2, 3, 4)
                },
            )
            self.assertEqual(project(fight, catalog=catalog), False)
            broken = dict(receipt, owner_id=-1)
            fight.native_ball_resource_constructor = broken
            with self.assertRaises(ValueError):
                validate_projection(fight, catalog=catalog)

        self.assertEqual(fight.actors[-7004].hp, 100)


if __name__ == "__main__":
    unittest.main()
