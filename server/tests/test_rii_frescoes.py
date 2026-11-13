"""Rii fresco bindings preserve native order and keep replay harmless."""
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from wakfu_server.achievements import mission_progress


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT / "server/wakfu_server/achievements/quest_interactions/rii_frescoes.json"
)


class RiiFrescoTests(unittest.TestCase):
    def test_three_frescoes_apply_native_order_and_rewards_once(self):
        records = json.loads(MANIFEST.read_text())["bindings"]
        self.assertEqual(
            [(26731, 10628), (26732, 10629), (26733, 10630)],
            [(r["object_id"], r["objective_id"]) for r in records],
        )
        definition = {
            "d": 5163,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjJ": [
                {"d": 10628, "ckc": "", "cke": ""},
                {"d": 10629, "ckc": "IsAchievementObjectiveComplete(10628)", "cke": ""},
                {"d": 10630, "ckc": "IsAchievementObjectiveComplete(10629)", "cke": ""},
            ],
            "cjK": [
                {"d": 9718, "aeV": 6, "ckl": [500]},
                {"d": 9719, "aeV": 2, "ckl": [413]},
            ],
        }
        state = {
            "variables": {},
            "objectives": [],
            "running": [5163],
            "completed": [],
            "tracking": [5163],
            "recent": [],
            "completion_dates": {},
        }
        character = {"id": 5, "account_id": 6}
        with self.assertRaisesRegex(ValueError, "prerequisite"):
            mission_progress.advance_objective(
                state, definition, 10629, character=character, store=None, now_ms=1
            )
        for offset, record in enumerate(records):
            state, rewards, added, completed = mission_progress.advance_objective(
                state,
                definition,
                record["objective_id"],
                character=character,
                store=None,
                now_ms=offset + 2,
            )
            self.assertEqual([record["objective_id"]], added)
            self.assertEqual([5163] if offset == 2 else [], completed)
            self.assertEqual(2 if offset == 2 else 0, len(rewards))
        self.assertEqual([10628, 10629, 10630], state["objectives"])
        self.assertEqual([5163], state["completed"])
        replay = mission_progress.advance_objective(
            state, definition, 10630, character=character, store=None, now_ms=6
        )
        self.assertEqual((state, [], [], []), replay)

    def test_script_index_uses_effect_reference_not_native_menu_action(self):
        spec = importlib.util.spec_from_file_location(
            "interactive_script_index",
            ROOT / "tools/quest-reconstruction/index_interactive_scripts.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            archive = directory / "scripts.jar"
            with zipfile.ZipFile(archive, "w") as scripts:
                scripts.writestr("genericIEActions/467.lua", "UI.displayFresco(0)\n")
            import csv

            objects = directory / "objects.csv"
            fields = [
                "map_id",
                "object_id",
                "type",
                "x",
                "y",
                "z",
                "native_outcome_definitions",
            ]
            with objects.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    dict(
                        map_id=1387,
                        object_id=26731,
                        type="GenericActivableInteractiveElement",
                        x=-21,
                        y=2,
                        z=4,
                        native_outcome_definitions=json.dumps(
                            {
                                "states": [
                                    {
                                        "action": 83,
                                        "outcomes": [{"effects": [{"class": 467}]}],
                                    }
                                ]
                            }
                        ),
                    )
                )
            result = module.index_scripts(archive, objects)
        self.assertEqual(
            {"function": "UI.displayFresco", "arguments": "0"}, result[467]["calls"][0]
        )
        self.assertEqual("26731", result[467]["objects"][0]["object_id"])
        self.assertEqual(83, result[467]["objects"][0]["native_action"])


if __name__ == "__main__":
    unittest.main()
