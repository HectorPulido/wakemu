"""Source-only pins for the native Astrub Magnum 2706→2707 chain."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wakfu_server.achievements import (
    conversation_story_authoring,
    mission_toolkit_contract,
    mission_toolkit_planner,
    source_quest_encounters,
)

ROOT = Path(__file__).resolve().parents[2]
WELL = (
    ROOT
    / "server/wakfu_server/achievements/quest_source_profiles/astrub-magnum-well.v1.json"
)
MISSION = (
    ROOT
    / "server/wakfu_server/achievements/mission_profiles/astrub-magnum-wet-night-followups.json"
)
CONVERSATION = (
    ROOT
    / "server/wakfu_server/achievements/conversation_archetypes/astrub_magnum_wet_night.json"
)
CANONICAL = ROOT / "server/wakfu_server/maps/native_quest_conversation_contracts.json"
NATIVE_EXPORT = ROOT / ".runtime/quest-extraction/native-quest-definitions.json"
DIALOGUES = ROOT / "database/protocol/npc-dialogues.json.gz"
OWNED = ROOT / "server/wakfu_server/maps/owned_story_profiles"


class AstrubMagnumSourceChainTests(unittest.TestCase):
    def test_native_wire_producers_rewards_and_2706_to_2707_admission_are_pinned(self):
        well = source_quest_encounters._read_document(WELL)
        source = well["bindings"][0]
        group = source["group"]
        action = source["action"]
        self.assertEqual((source["quest_id"], source["objective_id"]), (2706, 5340))
        self.assertEqual(
            (source["source"]["id"], source["source"]["map_id"]), (25457, 1134)
        )
        self.assertEqual(
            (group["id"], group["cog"], action["native_id"], action["wire_action"]),
            (1178, 0, 1200, 1),
        )
        self.assertIn(action, group["actions"])
        launch = next(
            effect for effect in action["effects"] if effect["effect_type"] == 10
        )
        self.assertEqual(
            (launch["action_reference"], launch["parameters"]), (2407, ["2040"])
        )
        self.assertEqual(source["scenario"]["id"], 2040)
        self.assertEqual(
            (source["scenario"]["win_event"], source["scenario"]["loss_event"]),
            (16120, 16122),
        )

        tampered = copy.deepcopy(well)
        tampered["bindings"][0]["action"]["wire_action"] = 0
        with tempfile.TemporaryDirectory() as temporary:
            bad_path = Path(temporary) / "tampered-well.json"
            bad_path.write_text(json.dumps(tampered))
            with self.assertRaisesRegex(ValueError, "exact native action group"):
                source_quest_encounters._read_document(bad_path)

        native = json.loads(NATIVE_EXPORT.read_text())
        native_definitions = {row["d"]: row for row in native["definitions"]}
        self.assertEqual(well["definitions"][0], native_definitions[2706])
        self.assertEqual(
            [(row["d"], row["ckl"]) for row in native_definitions[2706]["cjK"]],
            [(4287, [3000])],
        )
        self.assertEqual(
            [(row["d"], row["ckl"]) for row in native_definitions[2707]["cjK"]],
            [(4288, [8000]), (7228, [500])],
        )
        self.assertEqual(native_definitions[2706]["cjI"], "IsAchievementComplete(2705)")
        self.assertEqual(native_definitions[2707]["cjI"], "IsAchievementComplete(2706)")

        owned_native = json.loads(
            (OWNED / "astrub-night-1004.native.v1.json").read_text()
        )
        fire = owned_native["programs"]["25482"]
        wait_group = next(row for row in fire["groups"] if row["id"] == 1182)
        wait_action = wait_group["actions"][0]
        self.assertEqual(
            (
                wait_action["wire_action"],
                wait_group["cog"],
                wait_action["effects"][0]["action_reference"],
            ),
            (0, 3000, 2411),
        )
        return_group = next(row for row in fire["groups"] if row["id"] == 1183)
        return_action = return_group["actions"][0]
        return_effect = return_action["effects"][0]
        self.assertEqual(
            (
                return_action["wire_action"],
                return_group["cog"],
                return_effect["action_reference"],
            ),
            (1, 3000, 2412),
        )
        self.assertEqual(return_effect["parameters"], ["{35,84,0}", "1134", "3"])
        story = json.loads((OWNED / "astrub-night-1004.json").read_text())
        self.assertEqual(story["generic_returns"][0]["entry"]["wire_action"], 1)
        victory = next(step for step in story["steps"] if step["id"] == "night-victory")
        self.assertEqual(victory["kind"], "room_victory")
        self.assertEqual(
            victory["effects"],
            [{"kind": "quest_objective", "quest_id": 2706, "objective_id": 5341}],
        )

        profile = json.loads(MISSION.read_text())
        three_definitions = {
            identity: native_definitions[identity] for identity in (2705, 2706, 2707)
        }
        validated_profile = mission_toolkit_contract.validate(
            profile, three_definitions
        )
        state = {
            "variables": {},
            "tracking": [],
            "recent": [],
            "completion_dates": {},
            "running": [],
            "completed": [2706],
            "objectives": [],
        }
        with patch("wakfu_server.dungeon_criteria.evaluate", return_value=True):
            next_state, _, _, _ = mission_toolkit_planner.plan(
                state,
                three_definitions,
                validated_profile,
                {"kind": "quest_completed", "reference": 2706, "quantity": 1},
                character={"id": 19, "map_id": 1134, "level": 20},
                store=object(),
                now_ms=1,
            )
        self.assertEqual(next_state["running"], [2707])

        canonical = json.loads(CANONICAL.read_text())
        previous_actor = next(
            row
            for row in canonical["placements"]
            if row["row"]["actor_id"] == -1724034232352753
        )
        dialogues = json.loads(gzip.decompress(DIALOGUES.read_bytes()))
        compiled = conversation_story_authoring.extend(
            canonical,
            native_definitions,
            {row["id"]: row for row in dialogues["nodes"]},
            {row["ref"]: row for row in dialogues["speakers"]},
            json.loads(CONVERSATION.read_text()),
        )
        compiled_actor = next(
            row
            for row in compiled["placements"]
            if row["row"]["actor_id"] == -1724034232352753
        )
        self.assertEqual(compiled_actor["row"], previous_actor["row"])
        report = next(
            row
            for row in compiled["bindings"]
            if (row["quest_id"], row["objective_id"]) == (2707, 5342)
        )
        self.assertEqual(
            (
                report["reference_id"],
                report["action_id"],
                report["node_id"],
                report["choice_id"],
            ),
            (3819, 703, 3225, 8080),
        )
        for identity in (2706, 2707):
            self.assertEqual(
                next(row for row in compiled["definitions"] if row["d"] == identity)[
                    "cjK"
                ],
                native_definitions[identity]["cjK"],
            )


if __name__ == "__main__":
    unittest.main()
