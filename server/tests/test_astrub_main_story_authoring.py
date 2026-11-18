"""Main Astrub bootstrap earns progression from dialogue and owned completions."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import unittest

from wakfu_server.achievements import (
    conversation_story_authoring,
    mission_toolkit_contract,
    mission_toolkit_planner,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "server/wakfu_server"


def fixtures():
    definitions = {
        d["d"]: d
        for d in json.loads(
            (ROOT / "server/tests/fixtures/native_astrub_main_story.json").read_text()
        )["definitions"]
    }
    profile = json.loads(
        (
            BASE / "achievements/mission_profiles/astrub-main-story-followups.json"
        ).read_text()
    )
    return definitions, profile


def state(*, completed=(), running=()):
    return dict(
        variables={},
        objectives=[],
        running=list(running),
        completed=list(completed),
        active=sorted(set(completed) | set(running)),
        active_periods={},
        active_unknown=[],
        tracking=[],
        recent=[],
        completion_dates={str(q): 1000 for q in completed},
    )


def plan(current, event):
    definitions, profile = fixtures()
    return mission_toolkit_planner.plan(
        current,
        definitions,
        profile,
        event,
        character=dict(id=1, map_id=527, instance_id=0, level=1, effective_level=1),
        store=None,
        now_ms=2000,
    )


class AstrubMainStoryAuthoringTests(unittest.TestCase):
    def test_pappy_fragment_is_additive_and_binds_only_native_talk_not_external_steps(
        self,
    ):
        definitions, _profile = fixtures()
        document = json.loads(
            (BASE / "maps/native_quest_conversation_contracts.json").read_text()
        )
        native = json.loads(
            gzip.decompress(
                (ROOT / "database/protocol/npc-dialogues.json.gz").read_bytes()
            )
        )
        manifest = json.loads(
            (
                BASE / "achievements/conversation_archetypes/astrub_main_2165.json"
            ).read_text()
        )
        result = conversation_story_authoring.extend(
            document,
            definitions,
            {n["id"]: n for n in native["nodes"]},
            {s["ref"]: s for s in native["speakers"]},
            manifest,
        )
        self.assertEqual(result, document)
        self.assertEqual(
            [
                (b["quest_id"], b["objective_id"], b["node_id"], b["choice_id"])
                for b in result["bindings"]
                if b["quest_id"] in (2165, 2166, 2170)
            ],
            [(2165, 11546, 2745, 15270)],
        )
        placement = next(
            p for p in result["placements"] if p["row"]["actor_id"] == -2251799934992165
        )
        self.assertEqual(placement["available_quests_on_open"], [2165])
        self.assertEqual(placement["row"]["reference_id"], 1134)
        self.assertEqual(placement["row"]["action_ids"], [46])
        self.assertEqual(placement["interaction_anchor"], dict(x=38, y=2, z=4))
        for identity in (2165, 2166, 2170):
            self.assertIn(definitions[identity], result["definitions"])

    def test_followups_preserve_literal_native_parent_gates_and_actual_completion_events(
        self,
    ):
        definitions, profile = fixtures()
        mission_toolkit_contract.validate(profile, definitions)
        self.assertEqual(profile["bindings"], [])
        self.assertEqual(profile["links"], [])
        self.assertEqual(
            [
                (
                    a["event"]["kind"],
                    a["event"]["reference"],
                    a["quest_id"],
                    a["requires_completed"],
                )
                for a in profile["activations"]
            ],
            [
                ("quest_completed", 5568, 2165, [5568]),
                ("quest_completed", 2165, 2166, [2165]),
                ("quest_completed", 2166, 2170, [2166]),
            ],
        )
        self.assertEqual(
            [definitions[q]["cjI"] for q in (2165, 2166, 2170)],
            [
                "IsAchievementComplete(5568)",
                "IsAchievementComplete(2165)",
                "IsAchievementComplete(2166)",
            ],
        )

    def test_map_or_unearned_completion_event_cannot_start_the_main_chain(self):
        current = state()
        for event in (
            dict(kind="map_enter", reference=747, quantity=1),
            dict(kind="quest_completed", reference=5568, quantity=1),
        ):
            result = plan(current, event)
            self.assertEqual(result[0], current)
            self.assertEqual(result[1:], ([], [], []))

    def test_each_earned_parent_activates_only_next_native_quest_and_replay_is_inert(
        self,
    ):
        for completed, parent, child in (
            ([5568], 5568, 2165),
            ([5568, 2165], 2165, 2166),
            ([5568, 2165, 2166], 2166, 2170),
        ):
            with self.subTest(parent=parent):
                current = state(completed=completed)
                event = dict(kind="quest_completed", reference=parent, quantity=1)
                result = plan(current, event)
                self.assertEqual(result[0]["running"], [child])
                self.assertEqual(result[0]["completed"], completed)
                self.assertEqual(result[1:], ([], [], []))
                before = deepcopy(result[0])
                again = plan(before, event)
                self.assertEqual(again[0], before)
                self.assertEqual(again[1:], ([], [], []))


if __name__ == "__main__":
    unittest.main()
