"""Bounded timed-light lifecycle, with explicitly synthetic timing operands."""

from copy import deepcopy
import json
from pathlib import Path
import unittest
from collections import deque

from wakfu_server import owned_world_light_trial as trial
from wakfu_server import owned_object_trials


class WorldLightTrialTests(unittest.TestCase):
    def test_actual_labyrinth_actions_use_same_owned_reducer_and_only_final_exit_earns_objective(
        self,
    ):
        root = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server/maps/owned_object_trial_profiles"
        )
        selected = json.loads((root / "huppermage-labyrinth-1027.json").read_text())
        owned_object_trials.policy(dict(topology=dict(owned_object_trials=selected)))
        config = selected["trials"][0]["program"]
        state = owned_object_trials.initial_state(selected)
        result = owned_object_trials.reduce(
            selected,
            state,
            dict(
                kind="interact", source_id=26171, now_ms=1000, position=config["start"]
            ),
        )
        state = result["state"]
        self.assertNotIn("quest_objective", [r["kind"] for r in result["effects"]])
        for index, action in enumerate(config["representative_route"]):
            event = dict(action, now_ms=1100 + index * 100)
            result = owned_object_trials.reduce(selected, state, event)
            state = json.loads(
                json.dumps(result["state"])
            )  # reconnect-shaped checkpoint
            objectives = [
                effect
                for effect in result["effects"]
                if effect["kind"] == "quest_objective"
            ]
            self.assertEqual(
                [dict(kind="quest_objective", quest_id=2790, objective_id=5638)]
                if index == len(config["representative_route"]) - 1
                else [],
                objectives,
            )
        self.assertTrue(state["trials"]["light-labyrinth"]["complete"])
        self.assertEqual(
            [], owned_object_trials.reduce(selected, state, event)["effects"]
        )
        initial = owned_object_trials.initial_state(selected)
        active = owned_object_trials.reduce(
            selected,
            initial,
            dict(
                kind="interact", source_id=26171, now_ms=1000, position=config["start"]
            ),
        )["state"]
        expired = owned_object_trials.reduce(
            selected, active, dict(kind="tick", now_ms=121000)
        )
        self.assertFalse(
            expired["state"]["trials"]["light-labyrinth"].get("complete", False)
        )
        self.assertEqual(
            [dict(kind="relocate", position=config["start"])],
            [e for e in expired["effects"] if e["kind"] == "relocate"],
        )

    def test_timing_lamps_gate_trap_expiry_success_checkpoint_and_replay(self):
        root = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server/maps/owned_object_trial_profiles"
        )
        source = json.loads(
            (root / "huppermage-labyrinth-1027.sources.json").read_text()
        )
        geometry = json.loads(
            (root / "huppermage-labyrinth-1027.exploration.json").read_text()
        )
        self.assertEqual(source["lamp_source_ids"], list(range(26163, 26170)))
        self.assertTrue(source["native_trap_cells"])
        self.assertTrue(
            set(map(tuple, source["native_trap_cells"]))
            <= set(map(tuple, geometry["cells"]))
        )
        self.assertEqual(source["scenario"]["callbacks"]["exit_success"], 16515)
        # These small floor/time values isolate the generic reducer. They are
        # not asserted to be the original1027 timer, lamp quantity or gate join.
        cells = [[x, 0, 0] for x in range(4)]
        config = dict(
            schema=trial.SCHEMA,
            id="test-light",
            evidence="Synthetic reducer fixture",
            cells=cells,
            edges=[[a, b] for a, b in zip(cells, cells[1:])],
            start=cells[0],
            exit_cells=[cells[3]],
            trap_cells=[],
            duration_ms=1000,
            required_light=2,
            start_source=10,
            lamps=[dict(source_id=11, approaches=[cells[1]], light=2, extra_ms=500)],
            switches=[dict(source_id=12, approaches=[cells[2]])],
            gates=[dict(edge=[cells[2], cells[3]], switches=[12])],
        )
        frozen = deepcopy(config)
        state = trial.begin(config, now_ms=100, source_id=10, position=cells[0])

        def move(state, a, b, at=200):
            return trial.advance(
                config,
                state,
                dict(kind="move", **{"from": cells[a], "to": cells[b]}, now_ms=at),
            )

        at_lamp = move(state, 0, 1)["state"]
        with self.assertRaises(ValueError):
            trial.advance(
                config, state, dict(kind="interact", source_id=11, now_ms=200)
            )
        collected = trial.advance(
            config, at_lamp, dict(kind="interact", source_id=11, now_ms=250)
        )
        self.assertEqual(
            (2, 1600), (collected["state"]["light"], collected["state"]["deadline_ms"])
        )
        replay = trial.advance(
            config, collected["state"], dict(kind="interact", source_id=11, now_ms=250)
        )
        self.assertEqual(collected["state"], replay["state"])
        self.assertEqual([], replay["events"])
        before_gate = move(collected["state"], 1, 2, 300)["state"]
        with self.assertRaisesRegex(ValueError, "closed"):
            move(before_gate, 2, 3, 400)
        opened = trial.advance(
            config, before_gate, dict(kind="interact", source_id=12, now_ms=350)
        )["state"]
        restored = json.loads(json.dumps(opened))
        finished = move(restored, 2, 3, 400)
        self.assertEqual(
            ("success", ["success"]), (finished["state"]["stage"], finished["events"])
        )
        self.assertEqual(
            [],
            trial.advance(config, finished["state"], dict(kind="tick", now_ms=5000))[
                "events"
            ],
        )
        expired = trial.advance(config, state, dict(kind="tick", now_ms=1100))
        self.assertEqual(
            ("failed", cells[0]),
            (expired["state"]["stage"], expired["state"]["position"]),
        )
        self.assertNotIn("success", expired["events"])
        with self.assertRaisesRegex(ValueError, "monotonic"):
            trial.advance(config, state, dict(kind="tick", now_ms=99))
        no_lamp = move(move(state, 0, 1)["state"], 1, 2, 300)["state"]
        no_lamp = trial.advance(
            config, no_lamp, dict(kind="interact", source_id=12, now_ms=350)
        )["state"]
        self.assertEqual("active", move(no_lamp, 2, 3, 400)["state"]["stage"])
        trapped_config = {**config, "trap_cells": [cells[1]]}
        trapped = trial.advance(
            trapped_config,
            trial.begin(trapped_config, now_ms=100, source_id=10, position=cells[0]),
            dict(kind="move", **{"from": cells[0], "to": cells[1]}, now_ms=200),
        )
        self.assertEqual(
            ("active", cells[0], 1100),
            (
                trapped["state"]["stage"],
                trapped["state"]["position"],
                trapped["state"]["deadline_ms"],
            ),
        )
        self.assertEqual(frozen, config)

    def test_reconnect_restores_remaining_timer_and_spent_lamp_without_mutating_checkpoint(
        self,
    ):
        from wakfu_server import owned_world_light_program

        root = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server/maps/owned_object_trial_profiles"
        )
        selected = json.loads((root / "huppermage-labyrinth-1027.json").read_text())
        course = selected["trials"][0]
        config = course["program"]
        lamp = config["lamps"][0]
        start, goal = tuple(config["start"]), tuple(lamp["approaches"][0])
        edges = [(tuple(a), tuple(b)) for a, b in config["edges"]]
        traps = {tuple(cell) for cell in config["trap_cells"]}

        # Follow the actual directed native floor from the start to one lamp.
        pending = deque([start])
        previous = {start: None}
        while pending and goal not in previous:
            cell = pending.popleft()
            for origin, destination in edges:
                if (
                    origin == cell
                    and destination not in traps
                    and destination not in previous
                ):
                    previous[destination] = cell
                    pending.append(destination)
        self.assertIn(goal, previous)
        path = []
        cell = goal
        while cell is not None:
            path.append(cell)
            cell = previous[cell]
        path.reverse()

        program = trial.begin(
            config,
            now_ms=1000,
            source_id=config["start_source"],
            position=config["start"],
        )
        for index, (origin, destination) in enumerate(zip(path, path[1:]), start=1):
            program = trial.advance(
                config,
                program,
                dict(
                    kind="move",
                    **{"from": list(origin), "to": list(destination)},
                    now_ms=1000 + index * 250,
                ),
            )["state"]
        program = trial.advance(
            config,
            program,
            dict(kind="interact", source_id=lamp["source_id"], now_ms=2000),
        )["state"]
        self.assertEqual([lamp["source_id"]], program["lamps"])
        checkpoint = {"program": deepcopy(program)}
        before = deepcopy(checkpoint)

        effects = owned_world_light_program.reconnect_effects(
            course, checkpoint, now_ms=5000
        )
        self.assertEqual(before, checkpoint)
        self.assertEqual(
            [
                dict(
                    kind="scenario_event",
                    scenario=2075,
                    event=16495,
                    arguments=[146000],
                ),
                dict(
                    kind="scenario_event",
                    scenario=2075,
                    event=16492,
                    arguments=[30000, 1000, 5000, 1, 120000, lamp["source_id"]],
                ),
            ],
            effects,
        )
        self.assertEqual(
            [],
            owned_world_light_program.reconnect_effects(
                course, checkpoint, now_ms=program["deadline_ms"]
            ),
        )
