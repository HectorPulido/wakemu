"""The native level-130 School branch preserves its earned quest chain."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from wakfu_server.achievements import mission_toolkit_contract, mission_toolkit_planner
from wakfu_server.achievements import mission_progress
from test_mission_toolkit_core import state


ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads(
    (
        ROOT
        / "wakfu_server/achievements/mission_profiles/huppermage-school-third-year.json"
    ).read_text()
)
YEAR3 = json.loads(
    (ROOT / "tests/fixtures/native_school_year3_definitions.json").read_text()
)
YEAR2 = json.loads(
    (ROOT / "tests/fixtures/native_school_second_year_followups.json").read_text()
)
DEFINITIONS = list(YEAR3["definitions"])
DEFINITIONS.append(deepcopy(YEAR2["definitions"]["2787"]))
BY_ID = {row["d"]: row for row in DEFINITIONS}


class HuppermageSchoolThirdYearTests(unittest.TestCase):
    def test_level_130_native_introduction_chain_and_child_links_keep_registrar_gated(
        self,
    ):
        self.assertEqual(
            mission_toolkit_contract.validate(PROFILE, DEFINITIONS), PROFILE
        )
        character = {"id": 7, "map_id": 527, "level": 130}
        store = object()

        no_certificate = state()
        unchanged = deepcopy(no_certificate)
        result, intents, objectives, completed = mission_toolkit_planner.plan(
            no_certificate,
            DEFINITIONS,
            PROFILE,
            {"kind": "character_ready", "reference": 0, "quantity": 1},
            character=character,
            store=store,
            now_ms=1,
        )
        self.assertEqual(result, unchanged)
        self.assertEqual((intents, objectives, completed), ([], [], []))

        eligible = state(completed=(2787,))
        current, _, _, _ = mission_toolkit_planner.plan(
            eligible,
            DEFINITIONS,
            PROFILE,
            {"kind": "character_ready", "reference": 0, "quantity": 1},
            character=character,
            store=store,
            now_ms=2,
        )
        self.assertIn(2788, current["running"])
        self.assertNotIn(2789, current["running"])

        exclusive = state(running=(2789,), completed=(2787,))
        preserved, _, _, _ = mission_toolkit_planner.plan(
            exclusive,
            DEFINITIONS,
            PROFILE,
            {"kind": "character_ready", "reference": 0, "quantity": 1},
            character=character,
            store=store,
            now_ms=3,
        )
        self.assertIn(2789, preserved["running"])
        self.assertNotIn(2788, preserved["running"])

        intro_running = state(running=(2788,), completed=(2787,))
        intro_done, _, _, finished = mission_progress.advance_objective(
            intro_running, BY_ID[2788], 5636, character=character, store=store, now_ms=4
        )
        self.assertEqual(finished, [2788])
        self.assertIn(2788, intro_done["active"])
        current, _, _, _ = mission_toolkit_planner.plan(
            intro_done,
            DEFINITIONS,
            PROFILE,
            {"kind": "quest_completed", "reference": 2788, "quantity": 1},
            character=character,
            store=store,
            now_ms=5,
        )
        self.assertTrue({2790, 2797}.issubset(current["running"]))
        self.assertFalse({5646, 5647, 5648, 5643} & set(current["objectives"]))

        for previous, child_objective, next_quest, linked_objective in (
            (2790, 5638, 2791, 5646),
            (2791, 5650, 2792, 5647),
        ):
            current, _, _, finished = mission_progress.advance_objective(
                current,
                BY_ID[previous],
                child_objective,
                character=character,
                store=store,
                now_ms=10 + previous,
            )
            self.assertEqual(finished, [previous])
            current, _, added, _ = mission_toolkit_planner.plan(
                current,
                DEFINITIONS,
                PROFILE,
                {"kind": "quest_completed", "reference": previous, "quantity": 1},
                character=character,
                store=store,
                now_ms=20 + previous,
            )
            self.assertIn(next_quest, current["running"])
            self.assertEqual(added, [linked_objective])

        current, _, _, finished = mission_progress.advance_objective(
            current, BY_ID[2792], 5649, character=character, store=store, now_ms=30
        )
        self.assertEqual(finished, [2792])
        current, _, added, _ = mission_toolkit_planner.plan(
            current,
            DEFINITIONS,
            PROFILE,
            {"kind": "quest_completed", "reference": 2792, "quantity": 1},
            character=character,
            store=store,
            now_ms=40,
        )
        self.assertEqual(added, [5648])
        self.assertTrue({5646, 5647, 5648}.issubset(current["objectives"]))
        self.assertNotIn(5643, current["objectives"])
        self.assertNotIn(2797, current["completed"])

        self.assertEqual(
            [row["d"] for row in BY_ID[2797]["cjK"]], [4380, 7307, 7395, 9699]
        )
        self.assertEqual(
            [row["d"] for row in BY_ID[2797]["cjJ"]], [5646, 5647, 5648, 5643]
        )


if __name__ == "__main__":
    unittest.main()
