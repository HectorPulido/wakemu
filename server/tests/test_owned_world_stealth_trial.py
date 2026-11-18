"""Representative pure stealth matrix; all guards/turns are test fixtures."""

from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest

from wakfu_server import owned_world_stealth_trial as stealth


class OwnedWorldStealthTrialTests(unittest.TestCase):
    def test_actual_school_profile_movement_and_native_attack_share_owned_reducer(self):
        from wakfu_server import owned_object_trials as trials
        from wakfu_server import owned_world_stealth_program
        from wakfu_server.application import (
            owned_world_stealth_actor_dispatch as actors,
        )

        root = Path(__file__).resolve().parents[1]
        selected = json.loads(
            (
                root
                / "wakfu_server/maps/owned_object_trial_profiles/huppermage-infiltration-1028.json"
            ).read_text()
        )
        selected = trials.policy(dict(topology=dict(owned_object_trials=selected)))
        route = json.loads(
            (
                root / "tests/fixtures/school130_infiltration_acceptance_route.json"
            ).read_text()
        )["cells"]
        trial = selected["trials"][0]
        config = trial["program"]
        self.assertEqual(
            (1028, 2791, 5650),
            (
                selected["map_id"],
                selected["story_quest_id"],
                next(
                    effect["objective_id"]
                    for effect in trial["effects"]["success"]
                    if effect["kind"] == "quest_objective"
                ),
            ),
        )
        native_floor = json.loads(
            (
                root
                / "wakfu_server/maps/owned_object_trial_profiles/huppermage-infiltration-1028.exploration.json"
            ).read_text()
        )
        native_edges = {tuple(map(tuple, edge)) for edge in native_floor["edges"]}
        self.assertTrue(
            all(
                (tuple(left), tuple(right)) in native_edges
                for left, right in zip(route, route[1:])
            )
        )
        self.assertEqual(
            [12, 12, 16, 16, 20], [len(guard["patrol"]) for guard in config["guards"]]
        )
        initial = trials.initial_state(selected)
        prefix = trials.reduce(
            selected, initial, dict(kind="movement", cells=route[:20])
        )
        self.assertTrue(prefix["changed"])
        self.assertFalse(
            any(effect["kind"] == "quest_objective" for effect in prefix["effects"])
        )
        reconnected = json.loads(json.dumps(prefix["state"]))
        finished = trials.reduce(
            selected, reconnected, dict(kind="movement", cells=route[19:])
        )
        self.assertEqual(
            [dict(kind="quest_objective", quest_id=2791, objective_id=5650)],
            [
                effect
                for effect in finished["effects"]
                if effect["kind"] == "quest_objective"
            ],
        )
        self.assertTrue(finished["state"]["trials"][trial["id"]]["complete"])
        replay = trials.reduce(
            selected, finished["state"], dict(kind="movement", cells=route)
        )
        self.assertFalse(replay["changed"])
        self.assertEqual([], replay["effects"])

        # Test-only durable position fixture isolates the actual13130 consumer;
        # no live actor, inventory, quest or administrative victory is created.
        isolated = trials.initial_state(selected)
        guard = config["guards"][0]
        pose = guard["patrol"][0]
        program = stealth.begin(config, config["start"])
        program["position"] = list(pose["rear_cell"])
        isolated["trials"][trial["id"]] = dict(program=program)
        character = dict(
            id=5,
            account_id=6,
            map_id=1028,
            instance_id=(1 << 57) + 999,
            **dict(zip(("x", "y", "z"), pose["rear_cell"]))
        )
        identity = actors.actor_id(character["instance_id"], guard["id"])
        body = struct.pack(">qiihB", identity, *pose["position"], 0)
        event = actors.decode_attack(selected, isolated, character, body)
        self.assertEqual(dict(kind="stealth_attack", guard_id=guard["id"]), event)
        hit1 = trials.reduce(selected, isolated, event)
        hit2 = trials.reduce(selected, hit1["state"], event)
        status = hit2["state"]["trials"][trial["id"]]["program"]["guards"][
            str(guard["id"])
        ]
        self.assertEqual(2, status["hits"])
        self.assertFalse(
            any(effect["kind"] == "quest_objective" for effect in hit2["effects"])
        )
        with self.assertRaises(ValueError):
            actors.decode_attack(selected, hit2["state"], character, body)
        with self.assertRaises(ValueError):
            actors.decode_attack(
                selected, isolated, {**character, "x": character["x"] - 1}, body
            )
        with self.assertRaises(ValueError):
            actors.decode_attack(
                selected,
                isolated,
                character,
                struct.pack(
                    ">qiihB",
                    identity,
                    pose["position"][0] + 1,
                    *pose["position"][1:],
                    0
                ),
            )
        self.assertIsNone(
            actors.decode_attack(
                selected,
                isolated,
                character,
                struct.pack(">qiihB", identity + 1000, *pose["position"], 0),
            )
        )
        self.assertEqual(0, initial["revision"])
        self.assertEqual({}, initial["trials"])

    def test_path_vision_turns_rear_hits_alerts_checkpoint_and_terminal_matrix(self):
        # Explicit synthetic floor, poses and masks isolate the reusable rules.
        # They are not a recovered School1028 deployment or native turn schedule.
        cells = [[x, y, 0] for x in range(8) for y in range(5)]
        config = dict(
            schema=stealth.SCHEMA,
            id="synthetic-stealth-test",
            cells=cells,
            edges=[
                [left, right]
                for left in cells
                for right in cells
                if sum(abs(left[axis] - right[axis]) for axis in (0, 1)) == 1
            ],
            start=[0, 0, 0],
            exits=[[7, 0, 0]],
            evidence="Test-only grid, guard pose and turn schedule; no live source claim.",
            turn_boundary="authenticated_turn",
            detection_radius=3,
            suspicion_turns=2,
            rear_hits=2,
            alert_radius=3,
            neutralize_all_success=True,
            guards=[
                dict(
                    id=1,
                    patrol=[
                        dict(
                            position=[3, 2, 0],
                            rear_cell=[2, 2, 0],
                            vision_cells=[[4, 2, 0], [5, 2, 0]],
                        )
                    ],
                )
            ],
        )

        def move(current, path, declaration=config):
            return stealth.advance(
                declaration, current, dict(kind="movement", cells=path)
            )

        initial = stealth.begin(config, config["start"])
        frozen = deepcopy(initial)
        exit_result = move(initial, [[x, 0, 0] for x in range(8)])
        self.assertEqual("success", exit_result["state"]["stage"])
        self.assertEqual([dict(kind="success", reason="exit")], exit_result["events"])
        self.assertEqual(
            [],
            stealth.advance(config, exit_result["state"], dict(kind="turn"))["events"],
        )
        for event in (dict(kind="success"), dict(kind="ordinary_victory")):
            with self.subTest(forged=event), self.assertRaises(ValueError):
                stealth.advance(config, initial, event)
        with self.assertRaises(ValueError):
            move(initial, [[0, 0, 0], [7, 0, 0]])

        vision = move(
            initial,
            [
                [0, 0, 0],
                [1, 0, 0],
                [2, 0, 0],
                [3, 0, 0],
                [4, 0, 0],
                [4, 1, 0],
                [4, 2, 0],
                [4, 3, 0],
            ],
        )
        self.assertEqual("failed", vision["state"]["stage"])
        self.assertEqual([4, 2, 0], vision["state"]["position"])
        self.assertEqual("vision", vision["events"][-1]["reason"])
        self.assertEqual(config["start"], vision["events"][-1]["return_position"])

        rear_path = [[0, 0, 0], [1, 0, 0], [2, 0, 0], [2, 1, 0], [2, 2, 0]]
        rear = move(initial, rear_path)["state"]
        self.assertEqual(0, rear["guards"]["1"]["suspicion"])
        first_turn = stealth.advance(config, rear, dict(kind="turn"))["state"]
        self.assertEqual("active", first_turn["stage"])
        self.assertEqual(1, first_turn["guards"]["1"]["suspicion"])
        # A persisted reconnect keeps the consecutive-turn observation.
        restored = json.loads(json.dumps(first_turn))
        proximity = stealth.advance(config, restored, dict(kind="turn"))
        self.assertEqual("proximity", proximity["events"][-1]["reason"])
        far = move(first_turn, list(reversed(rear_path)))["state"]
        reset = stealth.advance(config, far, dict(kind="turn"))["state"]
        self.assertEqual(0, reset["guards"]["1"]["suspicion"])
        self.assertEqual(
            2, stealth.begin(config, config["start"], attempt=2)["attempt"]
        )

        with self.assertRaises(ValueError):
            stealth.advance(config, initial, dict(kind="rear_strike", guard_id=1))
        hit = dict(kind="rear_strike", guard_id=1)
        first_hit = stealth.advance(config, rear, hit)["state"]
        self.assertEqual(
            ("active", 1), (first_hit["stage"], first_hit["guards"]["1"]["hits"])
        )
        neutralized = stealth.advance(config, first_hit, hit)
        self.assertEqual("success", neutralized["state"]["stage"])
        self.assertEqual("guards", neutralized["events"][-1]["reason"])
        self.assertEqual(
            [], stealth.advance(config, neutralized["state"], hit)["events"]
        )

        crowded = deepcopy(config)
        crowded["guards"].append(
            dict(
                id=2,
                patrol=[
                    dict(
                        position=[3, 3, 0],
                        rear_cell=[2, 3, 0],
                        vision_cells=[[4, 3, 0]],
                    )
                ],
            )
        )
        crowded_rear = move(
            stealth.begin(crowded, crowded["start"]), rear_path, crowded
        )["state"]
        crowded_hit = stealth.advance(crowded, crowded_rear, hit)["state"]
        alert = stealth.advance(crowded, crowded_hit, hit)
        self.assertEqual("failed", alert["state"]["stage"])
        self.assertEqual("nearby_guard_alert", alert["events"][-1]["reason"])
        self.assertFalse(any(event["kind"] == "success" for event in alert["events"]))

        moving = deepcopy(config)
        moving["guards"][0]["patrol"].append(
            dict(
                position=[3, 3, 0],
                rear_cell=[2, 3, 0],
                vision_cells=[[4, 3, 0]],
            )
        )
        moved = stealth.advance(
            moving, stealth.begin(moving, moving["start"]), dict(kind="turn")
        )["state"]
        self.assertEqual(1, moved["guards"]["1"]["patrol_index"])
        with self.assertRaises(ValueError):
            stealth.advance(config, moved, dict(kind="turn"))
        malformed = deepcopy(initial)
        malformed["guards"]["1"]["patrol_index"] = 99
        with self.assertRaises(ValueError):
            stealth.advance(config, malformed, dict(kind="turn"))
        declined = stealth.advance(config, initial, dict(kind="decline"))
        self.assertEqual("declined", declined["state"]["stage"])
        self.assertEqual(
            [], stealth.advance(config, declined["state"], dict(kind="turn"))["events"]
        )
        self.assertEqual(frozen, initial)
