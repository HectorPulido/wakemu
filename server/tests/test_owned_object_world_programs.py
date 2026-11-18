"""Bounded reducers for sliding tiles and the native school resource course."""

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server import (
    owned_object_trial_effects,
    owned_object_trials,
    owned_world_resource_trial,
    owned_world_tile_trial,
)


ROOT = Path(__file__).resolve().parents[1] / "wakfu_server"
RESOURCE_COURSE = json.loads(
    (
        ROOT / "maps/owned_object_trial_profiles/huppermage-school-2786.resource.json"
    ).read_text()
)
TILE_CONFIGURATION = json.loads(
    (
        ROOT
        / "maps/owned_object_trial_profiles/huppermage-tiles-1025.configuration.json"
    ).read_text()
)


class OwnedObjectWorldProgramsTests(unittest.TestCase):
    def test_physical_trial_skips_only_unavailable_objective_prerequisites(self):
        from wakfu_server.achievements.mission_progress import (
            ObjectivePrerequisiteUnavailable,
        )

        selected = {"id": "huppermage-school-2786", "story_quest_id": 2786}
        character = {"id": 21, "account_id": 4, "instance_id": 55}
        state = {"running": [2785], "completed": []}
        effect = {"kind": "quest_objective", "quest_id": 2785, "objective_id": 5622}
        apply = owned_object_trial_effects.executor(selected)

        with (
            patch.object(
                owned_object_trial_effects.storage, "load_locked", return_value=state
            ),
            patch(
                "wakfu_server.achievements.owned_quest_encounters._advance",
                side_effect=ObjectivePrerequisiteUnavailable(
                    "prior native stage absent"
                ),
            ) as advance,
        ):
            self.assertEqual(apply(object(), object(), character, [effect]), [])
            advance.assert_called_once()

        with (
            patch.object(
                owned_object_trial_effects.storage, "load_locked", return_value=state
            ),
            patch(
                "wakfu_server.achievements.owned_quest_encounters._advance",
                side_effect=ValueError("malformed producer facts"),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "malformed producer facts"):
                apply(object(), object(), character, [effect])

    def test_tile_and_resource_programs_accept_only_native_paths_and_complete_once(
        self,
    ):
        tile = {
            "schema": "owned-world-tile-trial-v1",
            "cells": [[10, 10, 0], [11, 10, 0], [10, 11, 0], [11, 11, 0]],
            "edges": [[1, 0], [1, 3], [0, 2], [2, 3]],
            "initial": [1, 0, 2, 3],
            "goal": [0, 1, 2, 3],
            "evidence": "Synthetic unit board for the finite edge/permutation contract.",
        }
        resource = deepcopy(RESOURCE_COURSE)
        native_chest = resource["native_authority"]["chest_source"]
        source_id = native_chest["id"]
        self.assertEqual(source_id, 26172)
        source = {
            "id": source_id,
            "position": [
                int(native_chest["x"]),
                int(native_chest["y"]),
                int(native_chest["z"]),
            ],
            "descriptor_id": native_chest["descriptor_id"],
            "action": 0,
            "duration_ms": 0,
            "payload_sha256": resource["native_authority"]["chest_payload_sha256"],
            "approaches": [resource["chest_cells"][0]],
        }
        selected = {
            "schema": owned_object_trials.SCHEMA,
            "id": "synthetic-school-world-programs",
            "map_id": resource["map_id"],
            "maximum_members": 1,
            "sources": [source],
            "trials": [
                {
                    "id": "tiles",
                    "kind": "sliding_tiles",
                    "requires": [],
                    "sources": [],
                    "program": tile,
                    "effects": {
                        "begin": [],
                        "success": ["tile-complete"],
                        "failure": ["tile-declined"],
                    },
                },
                {
                    "id": "course",
                    "kind": "resource_course",
                    "requires": [],
                    "sources": [source_id],
                    "program": resource,
                    "effects": {
                        "begin": [],
                        "success": ["course-complete"],
                        "failure": ["course-failed"],
                    },
                },
            ],
        }
        config = {"topology": {"owned_object_trials": selected}}
        self.assertIs(owned_object_trials.policy(config), selected)

        # The exact source is part of the resource-course declaration. Omitting
        # or substituting the authentic chest identity cannot qualify the trial.
        missing_source = deepcopy(config)
        missing_source["topology"]["owned_object_trials"]["sources"] = []
        with self.assertRaisesRegex(ValueError, "original qualified chest"):
            owned_object_trials.policy(missing_source)

        # A tile move must use both the durable empty cell and a declared edge.
        tile_state = owned_object_trials.initial_state(selected)
        tile_start = tile["cells"][1]
        unchanged = deepcopy(tile_state)
        with self.assertRaisesRegex(ValueError, "qualified adjacent swap"):
            owned_object_trials.reduce(
                selected,
                tile_state,
                {"kind": "movement", "cells": [tile_start, tile["cells"][2]]},
            )
        self.assertEqual(tile_state, unchanged)
        solved = owned_object_trials.reduce(
            selected,
            tile_state,
            {"kind": "movement", "cells": [tile_start, tile["cells"][0]]},
        )
        self.assertEqual(
            solved["state"]["trials"]["tiles"]["program"]["tiles"], tile["goal"]
        )
        self.assertEqual(
            solved["state"]["trials"]["tiles"]["program"]["stage"], "success"
        )
        tile_replay = owned_object_trials.reduce(
            selected,
            solved["state"],
            {"kind": "movement", "cells": [tile_start, tile["cells"][0]]},
        )
        self.assertFalse(tile_replay["changed"])

        # Leaving the declared board declines that attempt without satisfying
        # the goal. The reducer does not mutate the caller's saved state.
        declined = owned_object_trials.reduce(
            selected,
            tile_state,
            {"kind": "movement", "cells": [tile_start, [99, 99, 0]]},
        )
        self.assertEqual(
            declined["state"]["trials"]["tiles"]["program"]["stage"], "declined"
        )
        self.assertEqual(tile_state, unchanged)

        # Run the declared manual route through the generic reducer. It must
        # reach the real far-side chest before opening it; the chest does not
        # itself skip the return course or complete the trial.
        state = owned_object_trials.initial_state(selected)
        route = resource["reviewed_reconstruction"]["manual_route"]
        begun = owned_object_trials.reduce(
            selected, state, {"kind": "movement", "cells": [route[0]]}
        )
        state = begun["state"]
        self.assertEqual(state["trials"]["course"]["program"]["stage"], "outward")
        with self.assertRaisesRegex(ValueError, "outward course completion"):
            owned_object_trials.reduce(
                selected, state, {"kind": "interact", "source_id": source_id}
            )

        refill_branches = set()
        for origin, destination in zip(route, route[1:]):
            before = state["trials"]["course"]["program"]["resource"]
            moved = owned_object_trials.reduce(
                selected,
                state,
                {"kind": "movement", "cells": [origin, destination]},
            )
            state = moved["state"]
            program = state["trials"]["course"]["program"]
            if destination in resource["bubbles"]:
                branch = (
                    "below" if before < resource["refill_threshold"] else "at_or_above"
                )
                refill_branches.add(branch)
                refill = (
                    resource["refill_below"]
                    if branch == "below"
                    else resource["refill_at_or_above"]
                )
                self.assertEqual(
                    program["resource"],
                    min(resource["capacity"], before + refill) - resource["decrement"],
                )
        self.assertEqual(refill_branches, {"below", "at_or_above"})
        self.assertEqual(state["trials"]["course"]["program"]["stage"], "chest")
        self.assertFalse(state["trials"]["course"].get("complete", False))

        # Once outward travel reaches the chest floor, ordinary accepted
        # movement may continue. It must update the saved pose without
        # advancing the course, spending resource, or granting its objective.
        far_side = list(route[-1])
        away_cell = list(route[-2])
        resource_at_chest = state["trials"]["course"]["program"]["resource"]
        away = owned_object_trials.reduce(
            selected,
            state,
            {"kind": "movement", "cells": [far_side, away_cell]},
        )
        state = away["state"]
        away_program = state["trials"]["course"]["program"]
        self.assertEqual(away_program["position"], away_cell)
        self.assertEqual(away_program["resource"], resource_at_chest)
        self.assertEqual(away_program["stage"], "chest")
        self.assertFalse(
            any(effect.get("objective_id") == 5632 for effect in away["effects"])
        )
        back = owned_object_trials.reduce(
            selected,
            state,
            {"kind": "movement", "cells": [away_cell, far_side]},
        )
        state = back["state"]
        back_program = state["trials"]["course"]["program"]
        self.assertEqual(back_program["position"], far_side)
        self.assertEqual(back_program["resource"], resource_at_chest)
        self.assertEqual(back_program["stage"], "chest")
        self.assertFalse(
            any(effect.get("objective_id") == 5632 for effect in back["effects"])
        )

        wrong_chest = owned_object_trials.reduce(
            selected, state, {"kind": "interact", "source_id": source_id + 1}
        )
        self.assertFalse(wrong_chest["changed"])
        opened = owned_object_trials.reduce(
            selected, state, {"kind": "interact", "source_id": source_id}
        )
        state = opened["state"]
        self.assertEqual(state["trials"]["course"]["program"]["stage"], "return")
        self.assertFalse(state["trials"]["course"].get("complete", False))
        for origin, destination in zip(route[::-1], route[-2::-1]):
            moved = owned_object_trials.reduce(
                selected,
                state,
                {"kind": "movement", "cells": [origin, destination]},
            )
            state = moved["state"]
        self.assertEqual(state["trials"]["course"]["program"]["stage"], "success")
        self.assertTrue(state["trials"]["course"]["complete"])
        replay = owned_object_trials.reduce(
            selected,
            state,
            {"kind": "interact", "source_id": source_id},
        )
        self.assertFalse(replay["changed"])

        # A zero-resource course fails on its first real move rather than
        # awarding a chest completion.
        exhausted = deepcopy(resource)
        exhausted["initial"] = 1
        failing = owned_world_resource_trial.begin(exhausted, exhausted["start"])
        failed = owned_world_resource_trial.advance(
            exhausted,
            failing,
            {"kind": "move", "from": exhausted["start"], "to": [0, -1, 0]},
        )
        self.assertEqual(failed["state"]["resource"], 0)
        self.assertEqual(failed["state"]["stage"], "failed")
        self.assertNotIn("success", failed["events"])

        # The checked-in School1025 board is bound to actual native exploration
        # cells and edges. Exercise its source-pinned empty tile, all 12 accepted
        # movement edges, and native26175 checkpoint from the same policy.
        actual = owned_object_trials.policy(TILE_CONFIGURATION)
        self.assertEqual(
            (actual["id"], actual["map_id"]), ("huppermage-tiles-1025", 1025)
        )
        actual_tile = next(
            trial for trial in actual["trials"] if trial["kind"] == "sliding_tiles"
        )
        checkpoint = next(
            trial for trial in actual["trials"] if trial["kind"] == "zone_checkpoint"
        )
        exploration = TILE_CONFIGURATION["topology"]["exploration_geometry"]
        floor = {tuple(point) for point in exploration["cells"]}
        walking_edges = {(tuple(a), tuple(b)) for a, b in exploration["edges"]}
        program = actual_tile["program"]
        board = list(map(tuple, program["cells"]))
        self.assertEqual(len(board), 16)
        self.assertTrue(set(board) <= floor)
        self.assertTrue(
            {(board[origin], board[target]) for origin, target in program["edges"]}
            <= walking_edges
        )
        solution = list(map(tuple, program["solution_cells"]))
        self.assertEqual(len(solution) - 1, 12)
        solution_edges = {(board[a], board[b]) for a, b in program["edges"]}
        self.assertTrue(set(zip(solution, solution[1:])) <= solution_edges)

        # A character can first enter the accepted movement stream on the
        # native edge immediately before the original blank tile. That starts
        # the board at the real empty cell without inventing a swap/objective.
        prefix_edge = ((0, -5, -2), (0, -6, -2))
        self.assertIn(prefix_edge, walking_edges)
        self.assertEqual(board[program["initial"].index(0)], prefix_edge[1])
        entry_state = owned_object_trials.initial_state(actual)
        entered = owned_object_trials.reduce(
            actual,
            entry_state,
            {"kind": "movement", "cells": [list(prefix_edge[0]), list(prefix_edge[1])]},
        )
        entry_program = entered["state"]["trials"][actual_tile["id"]]["program"]
        self.assertTrue(entered["changed"])
        self.assertEqual(entry_program["tiles"], program["initial"])
        self.assertEqual(entry_program["moves"], 0)
        self.assertEqual(entry_program["stage"], "active")
        self.assertTrue(
            any(effect["kind"] == "information" for effect in entered["effects"])
        )
        self.assertNotIn(
            {"kind": "quest_objective", "quest_id": 2785, "objective_id": 5622},
            entered["effects"],
        )

        zone_cells = {tuple(point) for point in checkpoint["destination_cells"]}
        self.assertEqual(checkpoint["destination_zone_ids"], [26175])
        self.assertTrue(zone_cells <= floor)
        zone_edge = next(
            (a, b) for a, b in sorted(walking_edges) if b in zone_cells and a in floor
        )
        checkpoint_state = owned_object_trials.initial_state(actual)
        ignored_endpoint = owned_object_trials.reduce(
            actual,
            checkpoint_state,
            {"kind": "movement", "cells": [list(zone_edge[1])]},
        )
        self.assertFalse(ignored_endpoint["changed"])
        accepted_checkpoint = owned_object_trials.reduce(
            actual,
            checkpoint_state,
            {"kind": "movement", "cells": [list(zone_edge[0]), list(zone_edge[1])]},
        )
        self.assertIn(
            {"kind": "quest_objective", "quest_id": 2786, "objective_id": 5625},
            accepted_checkpoint["effects"],
        )

        actual_state = owned_object_trials.initial_state(actual)
        started = owned_object_trials.reduce(
            actual,
            actual_state,
            {"kind": "movement", "cells": [list(solution[0])]},
        )
        actual_state = started["state"]
        self.assertIn(
            {"kind": "scenario_event", "scenario": 2072, "event": 16432},
            started["effects"],
        )
        for index, (origin, target_cell) in enumerate(zip(solution, solution[1:]), 1):
            moved = owned_object_trials.reduce(
                actual,
                actual_state,
                {"kind": "movement", "cells": [list(origin), list(target_cell)]},
            )
            actual_state = moved["state"]
            self.assertTrue(moved["changed"])
            complete_now = (
                actual_state["trials"][actual_tile["id"]]["program"]["stage"]
                == "success"
            )
            self.assertEqual(complete_now, index == 12)
        self.assertIn(
            {"kind": "quest_objective", "quest_id": 2785, "objective_id": 5622},
            moved["effects"],
        )
        self.assertTrue(actual_state["trials"][actual_tile["id"]]["complete"])
