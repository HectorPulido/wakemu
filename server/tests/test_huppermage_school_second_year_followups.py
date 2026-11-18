"""Staged School80 followups remain child-driven and registrar-gated."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from wakfu_server.achievements import mission_dependencies
from wakfu_server.achievements import mission_toolkit_contract, mission_toolkit_planner
from test_mission_toolkit_core import state


ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads(
    (
        ROOT
        / "wakfu_server/achievements/mission_profiles/huppermage-school-second-year-followups.json"
    ).read_text()
)
NATIVE = json.loads(
    (
        Path(__file__).parent / "fixtures/native_school_second_year_followups.json"
    ).read_text()
)
DEFINITIONS = list(NATIVE["definitions"].values())
BY_ID = {row["d"]: row for row in DEFINITIONS}


class HuppermageSchoolFollowupsTests(unittest.TestCase):
    def test_only_completed_2783_admits_parallel_branches_and_certificate_stays_registrar_gated(
        self,
    ):
        validated = mission_toolkit_contract.validate(PROFILE, DEFINITIONS)
        self.assertEqual(validated, PROFILE)
        self.assertEqual(
            {(row["objective_id"], row["child_quest_id"]) for row in PROFILE["links"]},
            {(5626, 2783), (5627, 2784), (5628, 2785), (5629, 2786)},
        )
        self.assertFalse(any(row["objective_id"] == 5635 for row in PROFILE["links"]))
        self.assertEqual(PROFILE["bindings"], [])

        character = {
            "id": 7,
            "account_id": 2,
            "level": 80,
            "map_id": 527,
            "instance_id": 0,
        }
        missing_seed = state(running=(2781,))
        untouched = deepcopy(missing_seed)
        result, intents, objectives, completed = mission_toolkit_planner.plan(
            missing_seed,
            DEFINITIONS,
            PROFILE,
            {"kind": "character_ready", "reference": 0, "quantity": 1},
            character=character,
            store=object(),
            now_ms=1,
        )
        self.assertEqual(result, untouched)
        self.assertEqual((intents, objectives, completed), ([], [], []))

        earned_seed = state(running=(2781,), completed=(2783,))
        original = deepcopy(earned_seed)
        current, intents, objectives, completed = mission_toolkit_planner.plan(
            earned_seed,
            DEFINITIONS,
            PROFILE,
            {"kind": "character_ready", "reference": 0, "quantity": 1},
            character=character,
            store=object(),
            now_ms=2,
        )
        self.assertEqual(earned_seed, original)
        self.assertTrue({2784, 2785, 2786, 2787}.issubset(current["running"]))
        self.assertIn(2781, current["running"])
        self.assertEqual((intents, completed), ([], []))
        self.assertIn(5626, current["objectives"])

        awarded_objectives = []
        for child, objective in ((2784, 5627), (2785, 5628), (2786, 5629)):
            current["running"].remove(child)
            if child in current["tracking"]:
                current["tracking"].remove(child)
            current["completed"].append(child)
            current, _intents, added, just_completed = mission_dependencies.reconcile(
                current,
                {row["d"]: row for row in DEFINITIONS},
                tuple(
                    (row["parent_quest_id"], row["objective_id"], row["child_quest_id"])
                    for row in PROFILE["links"]
                ),
                character=character,
                store=object(),
                now_ms=10 + child,
            )
            self.assertEqual(added, [objective])
            self.assertEqual(just_completed, [])
            awarded_objectives.extend(added)
            (
                replay,
                _replay_intents,
                replay_objectives,
                replay_completed,
            ) = mission_dependencies.reconcile(
                current,
                {row["d"]: row for row in DEFINITIONS},
                tuple(
                    (row["parent_quest_id"], row["objective_id"], row["child_quest_id"])
                    for row in PROFILE["links"]
                ),
                character=character,
                store=object(),
                now_ms=20 + child,
            )
            self.assertEqual((replay_objectives, replay_completed), ([], []))
            current = replay

        self.assertEqual(awarded_objectives, [5627, 5628, 5629])
        self.assertTrue({5626, 5627, 5628, 5629}.issubset(current["objectives"]))
        self.assertIn(2787, current["running"])
        self.assertNotIn(2787, current["completed"])
        self.assertNotIn(5635, current["objectives"])
        self.assertEqual(BY_ID[2787]["cjJ"][-1]["d"], 5635)


if __name__ == "__main__":
    unittest.main()
