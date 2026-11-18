"""Bounded native Wild Estate introduction, camp clues and approach proofs."""

from collections import deque
import json
from pathlib import Path
import unittest

from tools.install_quest_interactions import validate_manifest
from wakfu_server.achievements import (
    mission_progress,
    mission_toolkit_contract,
    mission_toolkit_planner,
)
from test_mission_toolkit_core import state


ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads(
    (
        ROOT / "wakfu_server/achievements/mission_profiles/wild-estate-initial.json"
    ).read_text()
)
INTERACTIONS = json.loads(
    (
        ROOT / "wakfu_server/achievements/quest_interactions/wild-estate-initial.json"
    ).read_text()
)
NATIVE = json.loads(
    (Path(__file__).parent / "fixtures/native_wild_estate_initial.json").read_text()
)
PATHS = json.loads(
    (
        Path(__file__).parent / "fixtures/native_wild_estate_initial_paths.json"
    ).read_text()
)


class WildEstateInitialTests(unittest.TestCase):
    def setUp(self):
        self.definitions = NATIVE["definitions"]
        self.by_id = {row["d"]: row for row in self.definitions}
        mission_toolkit_contract.validate(PROFILE, self.definitions)

    def plan(self, current, event, character, now_ms):
        return mission_toolkit_planner.plan(
            current,
            self.definitions,
            PROFILE,
            event,
            character=character,
            store=object(),
            now_ms=now_ms,
        )

    def test_level50_readiness_admits_only_current_introduction(self):
        event = {"kind": "character_ready", "reference": 0, "quantity": 1}
        below, *_ = self.plan(
            state(), event, dict(id=7, level=49, map_id=527, instance_id=0), 1
        )
        self.assertEqual(below["running"], [])

        admitted, *_ = self.plan(
            state(), event, dict(id=7, level=50, map_id=527, instance_id=0), 2
        )
        self.assertEqual(admitted["running"], [1686])
        self.assertNotIn(1612, admitted["running"])
        self.assertNotIn(1616, admitted["running"])
        self.assertNotIn(1617, admitted["running"])

        legacy = state(running=[1612])
        legacy["active"] = [1612]
        blocked, *_ = self.plan(
            legacy, event, dict(id=7, level=50, map_id=527, instance_id=0), 3
        )
        self.assertEqual(blocked["running"], [1612])

    def test_boat_arrival_completes_intro_then_camp_completion_starts_tracks_once(self):
        ready, *_ = self.plan(
            state(),
            {"kind": "character_ready", "reference": 0, "quantity": 1},
            dict(id=7, level=50, map_id=527, instance_id=0),
            10,
        )
        departure = self.plan(
            ready,
            {"kind": "map_departure", "reference": 711, "quantity": 1},
            dict(id=7, level=50, map_id=527, instance_id=0),
            11,
        )
        current, intents, objectives, completed = departure
        self.assertIn(1686, completed)
        self.assertIn(3170, objectives)
        self.assertIn(1686, current["completed"])
        self.assertNotIn(1616, current["running"])

        arrival = self.plan(
            current,
            {"kind": "map_enter", "reference": 711, "quantity": 1},
            dict(id=7, level=50, map_id=711, instance_id=0),
            12,
        )
        current, intents, objectives, completed = arrival
        self.assertIn(1616, current["running"])
        self.assertNotIn(1612, current["completed"])

        for objective_id in (3024, 3025, 3026):
            (
                current,
                intents,
                added,
                just_completed,
            ) = mission_progress.advance_objective(
                current,
                self.by_id[1616],
                objective_id,
                character=dict(id=7, level=50, map_id=711, instance_id=0),
                store=object(),
                now_ms=12 + objective_id,
            )
            self.assertIn(objective_id, added)
        self.assertIn(1616, just_completed)
        followup = self.plan(
            current,
            {"kind": "quest_completed", "reference": 1616, "quantity": 1},
            dict(id=7, level=50, map_id=711, instance_id=0),
            20,
        )
        after, followup_intents, followup_objectives, followup_completed = followup
        self.assertIn(1617, after["running"])
        self.assertEqual(followup_completed, [])
        replay = self.plan(
            after,
            {"kind": "quest_completed", "reference": 1616, "quantity": 1},
            dict(id=7, level=50, map_id=711, instance_id=0),
            21,
        )
        self.assertEqual(replay[0], after)
        self.assertEqual(replay[1:], ([], [], []))

    def test_seven_exact_clues_and_all_reviewed_approaches_are_native_and_reachable(
        self,
    ):
        records = validate_manifest(INTERACTIONS, "a" * 64)
        self.assertEqual(len(records), 7)
        expected = {
            20390: (1616, 3024, 442),
            20389: (1616, 3025, 450),
            20377: (1616, 3026, 451),
            20393: (1617, 3017, 455),
            20395: (1617, 3030, 456),
            20398: (1617, 3031, 457),
            20380: (1617, 3032, 445),
        }
        self.assertEqual(
            {
                row["object_id"]: (
                    row["quest_id"],
                    row["objective_id"],
                    row["script_id"],
                )
                for row in records
            },
            expected,
        )
        source_rows = NATIVE["native_sources"]["sources"]
        source_ids = {int(identity) for identity in source_rows}
        self.assertTrue(set(expected) <= source_ids)
        explicit_wrong = {20392, 20396, 20399, 20400, 20401, 20402}
        self.assertTrue(explicit_wrong <= source_ids)
        self.assertTrue(set(expected).isdisjoint(explicit_wrong))

        approved_approaches = {}
        for row in records:
            positions = {
                tuple(row["approach_cells"][index : index + 3])
                for index in range(0, len(row["approach_cells"]), 3)
            }
            native_positions = {
                tuple(position)
                for position in source_rows[str(row["object_id"])]["approaches"]
            }
            self.assertEqual(positions, native_positions)
            approved_approaches.update(
                {position: row["object_id"] for position in positions}
            )
        all_approaches = [
            tuple(position)
            for source in source_rows.values()
            for position in source["approaches"]
        ]
        self.assertEqual(len(all_approaches), 94)
        outgoing = {}
        for source, destination in PATHS["edges"]:
            outgoing.setdefault(tuple(source), set()).add(tuple(destination))
        reached = {tuple(PATHS["boat_arrival"])}
        pending = deque(reached)
        while pending:
            for destination in outgoing.get(pending.popleft(), ()):
                if destination not in reached:
                    reached.add(destination)
                    pending.append(destination)
        self.assertEqual(len(approved_approaches), 46)
        self.assertTrue(set(all_approaches) <= reached)


if __name__ == "__main__":
    unittest.main()
