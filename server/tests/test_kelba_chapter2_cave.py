"""Representative contracts for the native Kelba chapter-two cave slice."""
import json
from pathlib import Path
import unittest

from wakfu_server import owned_story_controller, owned_story_mechanics

ROOT = Path(__file__).resolve().parents[1]
STORY = ROOT / "wakfu_server/maps/owned_story_profiles"


def load(path):
    return json.loads(path.read_text())


class KelbaChapterTwoCaveTests(unittest.TestCase):
    def test_discovery_requires_original_cinematic_before_separate_native_talk(self):
        policy = owned_story_controller.policy(
            {
                "topology": {
                    "owned_story_controller": load(STORY / "kelba-cave-952.json")
                }
            }
        )
        native = owned_story_mechanics.sources(policy)
        self.assertEqual(native["scenario_id"], 1967)
        finished = set()
        start = owned_story_controller.plan(
            policy, finished, kind="world_ready", reference=952
        )
        self.assertEqual(start["effects"][0]["event"], 15832)
        self.assertFalse(any(e["kind"] == "quest_objective" for e in start["effects"]))
        finished.add(start["id"])
        for callback, following in [(15832, 15833), (15833, 15834), (19799, 19799)]:
            if callback != 19799:
                self.assertIsNone(
                    owned_story_controller.plan(
                        policy, finished, kind="scenario_complete", reference=19799
                    )
                )
            step = owned_story_controller.plan(
                policy, finished, kind="scenario_complete", reference=callback
            )
            self.assertEqual(step["effects"][0]["event"], following)
            finished.add(step["id"])
        self.assertEqual(
            [
                (e["quest_id"], e["objective_id"])
                for e in step["effects"]
                if e["kind"] == "quest_objective"
            ],
            [(2547, 5046), (2548, 5047)],
        )
        for quest, objective in [(2547, 5065), (2548, 5064)]:
            npc = load(
                ROOT
                / f"wakfu_server/maps/owned_story_npc_profiles/kelba-cave-952-{quest}.json"
            )
            self.assertEqual(npc["requires"], ["chapter2-discovered"])
            row = npc["npcs"][0]
            self.assertEqual(
                (
                    row["reference_id"],
                    row["action_ids"],
                    row["dialogue_root"],
                    row["choice_id"],
                    row["objective_id"],
                ),
                (3580, [673], 3149, 7804, objective),
            )
        geometry = load(STORY / "kelba-cave-952.exploration.json")
        self.assertEqual((len(geometry["cells"]), len(geometry["edges"])), (65, 208))
        self.assertIn([-2, 0, 0], geometry["cells"])
        self.assertEqual(native["scene_actors"][0]["until"], ["chapter2-discovered"])


if __name__ == "__main__":
    unittest.main()
