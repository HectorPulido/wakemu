"""Focused authoring checks for the mission toolkit CLI and core contract."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mission_toolkit
from wakfu_server.achievements import mission_toolkit_contract, mission_toolkit_planner

FIXTURE = ROOT / "tests" / "fixtures" / "mission_toolkit_non_rii.json"


def native_definitions():
    parent = {
        "d": 9001,
        "native_class": "aJM",
        "aqb": False,
        "cjI": "",
        "cjJ": [
            {
                "d": 9010,
                "native_class": "aJN",
                "ckb": True,
                "ckc": "IsAchievementComplete(9002)",
                "cke": "",
                "ckf": [],
            }
        ],
        "cjK": [],
    }
    child = {
        "d": 9002,
        "native_class": "aJM",
        "aqb": False,
        "cjI": "",
        "cjJ": [
            {
                "d": 9020,
                "native_class": "aJN",
                "ckb": True,
                "ckc": "",
                "cke": "",
                "ckf": [
                    {
                        "ckm": 'GetAchievementVariable("demo") >= 2',
                        "ckn": [7001],
                    }
                ],
            }
        ],
        "cjK": [],
    }
    return {9001: parent, 9002: child}


def empty_state():
    return {
        "variables": {},
        "tracking": [],
        "recent": [],
        "completion_dates": {},
        "running": [],
        "completed": [],
        "objectives": [],
    }


class MissionToolkitCliTests(unittest.TestCase):
    def test_non_rii_fixture_validates_and_runs_activation_event_link_chain(self):
        profile = json.loads(FIXTURE.read_text())
        definitions = native_definitions()
        validated = mission_toolkit_contract.validate(profile, definitions)
        self.assertEqual(
            mission_toolkit.validation_diagnostics(profile, definitions), []
        )
        character = {"id": 7, "map_id": 527, "level": 20}
        store = object()
        state = empty_state()

        state, _, _, _ = mission_toolkit_planner.plan(
            state,
            definitions,
            validated,
            {"kind": "dialogue", "reference": 5001, "quantity": 1},
            character=character,
            store=store,
            now_ms=1,
        )
        self.assertEqual(state["running"], [9001, 9002])
        self.assertEqual(state["variables"], {"7001": 0})

        for now_ms in (2, 3):
            state, _, _, completed = mission_toolkit_planner.plan(
                state,
                definitions,
                validated,
                {
                    "kind": "resource_harvest",
                    "reference": 40001,
                    "quantity": 1,
                },
                character=character,
                store=store,
                now_ms=now_ms,
            )
        self.assertEqual(state["completed"], [9001, 9002])
        self.assertEqual(state["objectives"], [9010, 9020])
        self.assertEqual(state["variables"]["7001"], 2)

    def test_scaffold_exposes_counter_threshold_without_guessing_producer(self):
        definitions = native_definitions()
        profile, candidates = mission_toolkit.scaffold_profile(
            "fixture.unresolved", [9002], definitions, instances=[0]
        )
        self.assertEqual(candidates[0]["native_threshold"], 2)
        self.assertEqual(
            candidates[0]["status"],
            "counter_candidate_only_needs_producer_binding",
        )
        self.assertEqual(profile["bindings"][0]["instances"], [0])
        self.assertEqual(profile["activations"][0]["instances"], [0])
        diagnostics = mission_toolkit.validation_diagnostics(profile, definitions)
        self.assertTrue(any("evidence" in text.lower() for text in diagnostics))
        self.assertTrue(
            any("needs an explicit producer binding" in text for text in diagnostics)
        )

    def test_partial_profile_is_valid_with_coverage_warnings_by_default(self):
        profile = json.loads(FIXTURE.read_text())
        profile["activations"] = []
        errors = mission_toolkit.validation_diagnostics(profile, native_definitions())
        warnings = mission_toolkit.coverage_warnings(profile, native_definitions())
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 2)
        self.assertTrue(
            any("Quest 9001 has no activation" in text for text in warnings)
        )
        self.assertTrue(
            any("Quest 9002 has no activation" in text for text in warnings)
        )

    def test_bulk_quest_reference_collection_includes_links(self):
        profile = {
            "bindings": [{"quest_id": 9001}],
            "activations": [{"quest_id": 9002}],
            "links": [
                {"parent_quest_id": 9003, "child_quest_id": 9004},
                {"parent_quest_id": "bad", "child_quest_id": 9004},
            ],
        }
        self.assertEqual(
            mission_toolkit.referenced_quest_ids(profile), [9001, 9002, 9003, 9004]
        )

    def test_producer_coverage_labels_match_current_integration_scope(self):
        self.assertIn("dungeon_completed", mission_toolkit.VERIFIED_WIRED_PRODUCERS)
        self.assertIn("item_delivery", mission_toolkit.SCOPED_WIRED_PRODUCERS)
        self.assertIn(
            "recipe-batch executions",
            mission_toolkit.VERIFIED_WIRED_PRODUCERS["craft_completed"],
        )
        self.assertNotIn("scenario_completed", mission_toolkit.VERIFIED_WIRED_PRODUCERS)
        self.assertNotIn("scenario_completed", mission_toolkit.SCOPED_WIRED_PRODUCERS)

    def test_strict_completeness_rejects_declared_only_but_allows_internal_activation(
        self,
    ):
        scenario = {
            "id": "future-scenario",
            "quest_id": 9002,
            "objective_id": 9020,
            "event": {"kind": "scenario_completed", "reference": 12},
            "count": "operation",
        }
        profile = {"bindings": [scenario], "activations": [], "links": []}
        default_warnings = mission_toolkit.coverage_warnings(
            profile, native_definitions()
        )
        self.assertTrue(
            any(
                "scenario_completed" in warning and "declared-only" in warning
                for warning in default_warnings
            )
        )
        self.assertTrue(mission_toolkit.strict_producer_errors(profile))

        profile["bindings"] = []
        profile["activations"] = [
            {
                "id": "dependency-start",
                "quest_id": 9002,
                "event": {"kind": "quest_completed", "reference": 9001},
            }
        ]
        self.assertEqual(mission_toolkit.strict_producer_errors(profile), [])


if __name__ == "__main__":
    unittest.main()
