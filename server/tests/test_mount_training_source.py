"""Optional native training declares travel separately from genuine capture."""
import json
from pathlib import Path
import unittest

from wakfu_server import generic_transports, owned_story_controller as controller
from wakfu_server import owned_story_mechanics
from wakfu_server.achievements import mission_toolkit_contract

ROOT = Path(__file__).resolve().parents[1] / "wakfu_server"
SLUG = "astrub-mount-training-879"


class MountTrainingSourceTests(unittest.TestCase):
    def test_original_gate_source_form_and_capture_producer_stay_distinct(self):
        config = json.loads(
            (
                ROOT / ("maps/owned_story_profiles/" + SLUG + ".configuration.json")
            ).read_text()
        )
        selected = controller.policy(config)
        source = owned_story_mechanics.sources(selected)
        route = config["route"]
        self.assertEqual(
            (
                route["entry_map_id"],
                route["entry_object_id"],
                route["destination_id"],
                route["start_map_id"],
            ),
            (527, 22995, 1796, 879),
        )
        self.assertEqual(route["criterion"], "IsAchievementRunning(2014)")
        gate = generic_transports.source(527, 22995)
        self.assertEqual(gate["approach_positions"], [dict(x=-87, y=-55, z=0)])
        self.assertEqual(source["objects"][0]["id"], 22858)
        self.assertEqual(
            selected["admission"],
            dict(quest_id=2014, objective_id=4103, continuation_quest_id=2014),
        )
        self.assertIsNone(
            controller.plan(selected, set(), kind="room_victory", reference=1)
        )
        ready = controller.plan(selected, set(), kind="world_ready", reference=879)
        self.assertEqual(ready["effects"], [])
        win = controller.plan(selected, {ready["id"]}, kind="room_victory", reference=1)
        self.assertEqual(
            win["effects"],
            [dict(kind="quest_objective", quest_id=2014, objective_id=4074)],
        )
        self.assertEqual(
            selected["capture_qualification"][0]["native_effect_reference"], 117956
        )
        (room,) = config["topology"]["rooms"]
        scene = room["encounter_scene"]
        self.assertEqual(
            [(r["state_id"], r["level"]) for r in scene["controlled_state_programs"]],
            [(2998, 1)],
        )
        self.assertEqual(scene["fixed_actor_placements"][0]["reference"], 3173)
        self.assertIn(scene["fixed_actor_placements"][0]["cell"], room["cells"])

    def test_independent_optional_admission_keeps_native_level_and_book_prerequisites(
        self,
    ):
        profile = json.loads(
            (
                ROOT / "achievements/mission_profiles/astrub-mount-training.json"
            ).read_text()
        )
        fixture = Path(__file__).with_name("fixtures")
        definitions = json.loads(
            (fixture / "native_mount_precursor_definitions.json").read_text()
        )["definitions"]
        definitions += json.loads(
            (fixture / "native_mount_training_2014.json").read_text()
        )["definitions"]
        validated = mission_toolkit_contract.validate(
            profile, {row["d"]: row for row in definitions}
        )
        self.assertTrue(
            all(row["quest_id"] == 2014 for row in validated["activations"])
        )
        recovery = next(
            row
            for row in validated["activations"]
            if row["event"]["kind"] == "character_ready"
        )
        self.assertEqual(
            (recovery["minimum_level"], recovery["requires_completed"]), (35, [2013])
        )
        self.assertEqual(validated["bindings"], [])
        self.assertEqual(validated["links"], [])
        books = json.loads(
            (ROOT / "achievements/mission_profiles/astrub-mount-books.json").read_text()
        )
        self.assertFalse(
            any(
                2014 in row.get("requires_completed", [])
                for row in books["activations"]
            )
        )
