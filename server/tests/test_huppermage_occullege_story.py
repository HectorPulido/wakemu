"""Original Occullege travel and terminal producer stay separate from visits."""
import json
from pathlib import Path
import struct
import unittest

from wakfu_server import owned_story_controller as controller
from wakfu_server import owned_story_mechanics, owned_story_native_links

ROOT = Path(__file__).resolve().parents[1] / "wakfu_server/maps/owned_story_profiles"
SLUG = "huppermage-occullege-1029"


class OccullegeStoryTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / (SLUG + ".json")).read_text())
        self.configuration = json.loads(
            (ROOT / (SLUG + ".configuration.json")).read_text()
        )

    def test_native_entry_four_portals_exits_and_reconnect_source_are_pinned(self):
        selected = controller.policy(self.configuration)
        self.assertEqual(selected, self.profile)
        native = owned_story_mechanics.sources(selected)
        route = self.configuration["route"]
        self.assertEqual(
            (
                route["entry_map_id"],
                route["entry_object_id"],
                route["destination_id"],
                route["start_map_id"],
            ),
            (1017, 26218, 2356, 1029),
        )
        self.assertEqual(len(self.configuration["topology"]["rooms"]), 4)
        for source, destination, room in [
            (26277, 2376, 1),
            (26278, 2377, 2),
            (26279, 2378, 3),
            (26280, 2379, 4),
        ]:
            body = struct.pack(">qiBi", source, destination, 0, 2)
            link = owned_story_native_links.selected_link(selected, body)
            self.assertEqual(
                link["requires"],
                ["occullege-entered"]
                if room == 1
                else [f"occullege-room-{room-1}-won"],
            )
            (target,) = native["teleporters"][str(source)]["destinations"]
            self.assertEqual(target["map_id"], 1029)
            self.assertIn(
                [target[k] for k in ("x", "y", "z")],
                self.configuration["topology"]["exploration_geometry"]["cells"],
            )
        self.assertEqual(
            {
                row["source_id"]
                for row in self.configuration["topology"]["native_story_exits"]
            },
            {26193, 26198, 26199, 26200, 26201},
        )
        self.assertEqual(
            controller.presentation_state(selected, {"occullege-entered"}), ()
        )

    def test_only_ordered_final_room_outcome_grants5649_and_never2797_registrar(self):
        selected = self.profile
        complete = set()
        self.assertIsNone(
            controller.plan(selected, complete, kind="room_victory", reference=4)
        )
        entry = controller.plan(selected, complete, kind="world_ready", reference=1029)
        self.assertFalse(
            any(effect.get("kind") == "quest_objective" for effect in entry["effects"])
        )
        complete.add(entry["id"])
        for order in range(1, 5):
            self.assertIsNone(
                controller.plan(
                    selected, complete, kind="scenario_complete", reference=16552
                )
            )
            step = controller.plan(
                selected, complete, kind="room_victory", reference=order
            )
            self.assertIsNotNone(step)
            credits = [
                effect
                for effect in step["effects"]
                if effect["kind"] == "quest_objective"
            ]
            self.assertEqual(
                credits,
                [dict(kind="quest_objective", quest_id=2792, objective_id=5649)]
                if order == 4
                else [],
            )
            complete.add(step["id"])
            self.assertIsNone(
                controller.plan(
                    selected, complete, kind="room_victory", reference=order
                )
            )
        self.assertEqual(
            len(self.configuration["compiled_plan"]["rooms"][-1]["monsters"]), 5
        )
        self.assertEqual(
            sum(
                row["count"]
                for row in self.configuration["compiled_plan"]["rooms"][-1]["monsters"]
            ),
            7,
        )
        self.assertFalse(
            any(
                effect.get("quest_id") == 2797
                for step in selected["steps"]
                for effect in step["effects"]
            )
        )
