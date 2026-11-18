"""The archaeology failure adapter preserves native feedback and timing."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_object_trials as trials
from wakfu_server.maps import owned_object_trial_effects
from wakfu_server.achievements import storage, tutorial_presentation_once


ROOT = Path(__file__).parents[1] / "wakfu_server/maps/owned_object_trial_profiles"


class OwnedObjectTrialEffectsTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / "archaeology-2698.json").read_text())
        self.selected = trials.policy(
            {"topology": {"owned_object_trials": self.profile}}
        )

    def test_native_failure_regions_and_base_failure_feed_back_without_repeating_scene(
        self,
    ):
        trial = self.selected["trials"][2]
        state = trials.initial_state(self.selected)
        state["trials"] = {
            "chronological-scrolls": {"complete": True},
            "ancient-relic-identification": {"complete": True},
            "fragile-relic-carry": {"carrying": True},
        }
        # Height violation at an attested native region selects its exact Lua
        # presentation; hazard failure uses the generic native break scene.
        region = trial["failure_regions"][0]
        bad_height = tuple(region["cells"][0])
        reduced = trials.reduce(
            self.selected,
            state,
            dict(
                kind="movement",
                cells=[
                    [bad_height[0], bad_height[1], bad_height[2] + 3],
                    list(bad_height),
                ],
            ),
        )
        self.assertEqual(reduced["effects"][0]["kind"], "relocate")
        self.assertEqual(reduced["effects"][1]["kind"], "information")
        self.assertEqual(reduced["effects"][2]["event"], 16211)

        hazard = tuple(trial["hazard_cells"][0])
        reduced_hazard = trials.reduce(
            self.selected,
            state,
            dict(kind="movement", cells=[list(hazard)]),
        )
        self.assertEqual(reduced_hazard["effects"][0]["kind"], "relocate")
        self.assertEqual(reduced_hazard["effects"][1]["kind"], "information")
        self.assertEqual(reduced_hazard["effects"][2]["event"], 16188)

        native = json.loads(
            (
                Path(__file__).parents[1]
                / "wakfu_server/maps/owned_story_profiles/archaeology-1001.native.v1.json"
            ).read_text()
        )
        character = dict(id=9, instance_id=88)
        store = SimpleNamespace(now=lambda: datetime(2026, 11, 15, tzinfo=timezone.utc))
        apply = owned_object_trial_effects.executor(self.selected)
        claim = Mock(side_effect=[True, False])
        move = Mock(return_value=(13530, b"relocated"))
        from wakfu_server import ecology_feedback

        information = Mock(return_value=(349, b"retry information"))
        with patch.object(
            owned_object_trial_effects.owned_story_mechanics,
            "sources",
            return_value=native,
        ), patch.object(
            storage, "load_locked", return_value=dict(running=[2698], completed=[])
        ), patch.object(
            tutorial_presentation_once, "claim", claim
        ), patch.object(
            owned_object_trial_effects.owned_story_mechanics, "move", move
        ), patch.object(
            ecology_feedback, "information", information
        ):
            first = apply("db", store, character, reduced_hazard["effects"])
            second = apply("db", store, character, reduced_hazard["effects"])

        self.assertEqual(sum(packet[0] == 13411 for packet in first), 1)
        self.assertEqual(sum(packet[0] == 13411 for packet in second), 0)
        self.assertEqual(
            first.presentation_due_ms, int(store.now().timestamp() * 1000) + 2100
        )
        self.assertEqual(second.presentation_due_ms, 0)
        self.assertEqual(move.call_count, 2)
        self.assertEqual(information.call_count, 2)
        self.assertEqual(claim.call_count, 2)
        self.assertTrue(any(packet[0] == 13530 for packet in first))
        self.assertTrue(any(packet[0] == 13530 for packet in second))
        self.assertTrue(any(packet[0] == 349 for packet in first))
        self.assertTrue(any(packet[0] == 349 for packet in second))


if __name__ == "__main__":
    unittest.main()
