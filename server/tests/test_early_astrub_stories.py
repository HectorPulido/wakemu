"""Crypt/nest declarations bind actual native rooms, gates and earned outcomes."""

from pathlib import Path
import hashlib
import json
import unittest

from wakfu_server import owned_story_controller as controller
from wakfu_server.owned_story_configuration import compile_story
from wakfu_server.combat_geometry import prepare_geometry, reachable
from wakfu_server.achievements import mission_toolkit_contract

ROOT = Path(__file__).parents[1]
PROFILES = ROOT / "wakfu_server/maps/owned_story_profiles"


class EarlyAstrubStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geometry = json.loads(
            (ROOT / "tests/fixtures/native_astrub_crypt_nest_geometry.json").read_text()
        )
        cls.monsters = {
            int(k): v
            for k, v in json.loads(
                (
                    ROOT / "tests/fixtures/native_astrub_crypt_nest_monsters.json"
                ).read_text()
            ).items()
        }
        cls.sources = {
            (r["map_id"], r["id"]): r
            for r in json.loads(
                (
                    ROOT / "tests/fixtures/native_astrub_crypt_nest_sources.json"
                ).read_text()
            )
        }

    def data(self, slug):
        manifest = json.loads((PROFILES / (slug + ".instance.json")).read_text())
        selected = json.loads((PROFILES / manifest["controller_file"]).read_text())
        encounters = json.loads((PROFILES / manifest["encounters_file"]).read_text())
        exploration = json.loads((PROFILES / manifest["exploration_file"]).read_text())
        return manifest, selected, encounters, exploration

    def test_crypt_followup_imports_native_prerequisite_and_requires_actual_completion(
        self,
    ):
        definitions = json.loads(
            (ROOT / "tests/fixtures/native_astrub_low_level_contracts.json").read_text()
        )["definitions"]
        profile = json.loads(
            (
                ROOT
                / "wakfu_server/achievements/mission_profiles/astrub-crypt-followup.json"
            ).read_text()
        )
        mission_toolkit_contract.validate(profile, definitions)
        self.assertEqual(len(profile["activations"]), 1)
        activation = profile["activations"][0]
        self.assertEqual(activation["quest_id"], 2161)
        self.assertEqual(
            activation["event"], dict(kind="quest_completed", reference=2160)
        )
        self.assertEqual(activation["requires_completed"], [2160])

    def test_complete_native_configs_preserve_entrances_rosters_grades_and_free_exit_alternatives(
        self,
    ):
        for slug, mapid, quest, objective, continuation, entry, exits in [
            ("astrub-crypt-889", 889, 2160, 4279, 2161, (19411, 1249), {23618}),
            ("astrub-nest-728", 728, 2162, 4283, 2162, (20653, 1441), {20652, 26431}),
        ]:
            with self.subTest(map=mapid):
                manifest, selected, encounters, exploration = self.data(slug)
                config = compile_story(
                    manifest,
                    controller=selected,
                    encounters=encounters,
                    geometry=prepare_geometry(self.geometry[str(mapid)]["geometry"]),
                    exploration=exploration,
                    sources=self.sources,
                    monster=self.monsters.__getitem__,
                )
                frozen = json.loads(
                    (PROFILES / (slug + ".configuration.json")).read_text()
                )
                self.assertEqual(config, frozen)
                self.assertEqual(
                    config["route"]["criterion"], manifest["native_entry_criterion"]
                )
                self.assertEqual(
                    (
                        config["route"]["entry_object_id"],
                        config["route"]["destination_id"],
                    ),
                    entry,
                )
                self.assertEqual(
                    selected["admission"],
                    dict(
                        quest_id=quest,
                        objective_id=objective,
                        continuation_quest_id=continuation,
                    ),
                )
                self.assertEqual(len(config["compiled_plan"]["rooms"]), 3)
                self.assertEqual(
                    {r["source_id"] for r in config["topology"]["native_story_exits"]},
                    exits,
                )
                self.assertTrue(
                    all(
                        r["criterion"] == ""
                        for r in config["topology"]["native_story_exits"]
                    )
                )
                self.assertFalse(config["compiled_plan"]["official"])
                self.assertEqual(
                    hashlib.sha256(
                        (PROFILES / selected["native_sources"]["path"]).read_bytes()
                    ).hexdigest(),
                    selected["native_sources"]["sha256"],
                )
                for room in config["compiled_plan"]["rooms"]:
                    for actor in room["monsters"]:
                        native = self.monsters[actor["ref_id"]]
                        self.assertEqual(
                            (actor["native_min_level"], actor["native_max_level"]),
                            (native["min_level"], native["max_level"]),
                        )
                        self.assertNotIn("hp", actor)
                        self.assertNotIn("spells", actor)
                self.assertEqual(
                    config["compiled_plan"]["rooms"][-1]["monsters"][0]["role"], "boss"
                )

    def test_room_victories_open_the_same_door_visual_and_native_collision_before_next_room(
        self,
    ):
        for slug, mapid, entry, room2, room3 in [
            ("astrub-crypt-889", 889, (0, 14, 0), (5, -39, -12), (19, -9, 0)),
            ("astrub-nest-728", 728, (0, 51, 0), (-1, 18, 0), (-1, -7, 0)),
        ]:
            with self.subTest(map=mapid):
                _, selected, _, exploration = self.data(slug)
                walking = prepare_geometry(exploration)
                masks = self.geometry[str(mapid)]["door_masks"]

                def can_reach(goal, done):
                    projection = controller.presentation_state(selected, done)
                    closed = {
                        tuple(p)
                        for e in projection
                        if e["blocks_movement"]
                        for p in masks[str(e["object_id"])]
                    }
                    for e in projection:
                        self.assertEqual(e["state"], int(e["blocks_movement"]))
                    return goal in reachable(
                        entry, walking.cells - closed, walking.outgoing
                    )

                self.assertFalse(can_reach(room2, set()))
                self.assertFalse(can_reach(room3, set()))
                self.assertIsNone(
                    controller.plan(selected, set(), kind="room_victory", reference=3)
                )
                first = controller.plan(
                    selected, set(), kind="room_victory", reference=1
                )
                done = {first["id"]}
                self.assertTrue(can_reach(room2, done))
                self.assertFalse(can_reach(room3, done))
                second = controller.plan(
                    selected, done, kind="room_victory", reference=2
                )
                done.add(second["id"])
                self.assertTrue(can_reach(room3, done))
                final = controller.plan(
                    selected, done, kind="room_victory", reference=3
                )
                done.add(final["id"])
                self.assertIsNone(
                    controller.plan(selected, done, kind="room_victory", reference=3)
                )
                self.assertTrue(can_reach(room3, done))

    def test_only_earned_final_crypt_and_ordered_larva_clear_emit_native_objectives(
        self,
    ):
        _, crypt, _, _ = self.data("astrub-crypt-889")
        crypt_objectives = [
            (step["reference"], effect["quest_id"], effect["objective_id"])
            for step in crypt["steps"]
            for effect in step["effects"]
            if effect["kind"] == "quest_objective"
        ]
        self.assertEqual(crypt_objectives, [(3, 2161, 4280)])
        self.assertFalse(
            any(
                e.get("event") in (14374, 14358)
                for s in crypt["steps"]
                for e in s["effects"]
            )
        )
        _, nest, _, _ = self.data("astrub-nest-728")
        nest_objectives = [
            (step["reference"], effect["quest_id"], effect["objective_id"])
            for step in nest["steps"]
            for effect in step["effects"]
            if effect["kind"] == "quest_objective"
        ]
        self.assertEqual(nest_objectives, [(2, 2162, 4284), (3, 2162, 4285)])
        self.assertFalse(
            any(
                e["kind"] == "scenario_event"
                for s in nest["steps"]
                for e in s["effects"]
            )
        )


if __name__ == "__main__":
    unittest.main()
