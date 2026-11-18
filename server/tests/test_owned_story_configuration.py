"""Multi-room story compilation preserves native travel, walking and rosters."""

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server import generic_transports, dungeon_runtime
from wakfu_server import owned_object_trials, owned_story_controller
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.monsters import reference
from wakfu_server.owned_story_configuration import compile_story


class StoryConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"
        cls.manifest = json.loads(
            (root / "astrub-temple-887.instance.json").read_text()
        )
        cls.controller = json.loads(
            (root / cls.manifest["controller_file"]).read_text()
        )
        cls.encounters = json.loads(
            (root / cls.manifest["encounters_file"]).read_text()
        )
        cls.exploration = json.loads(
            (root / cls.manifest["exploration_file"]).read_text()
        )
        cls.geometry = published_geometry(887)
        cls.sources = {
            (row["map_id"], row["id"]): row for row in generic_transports._CATALOG
        }

    def compile(self, **kwargs):
        return compile_story(
            kwargs.get("manifest", self.manifest),
            controller=kwargs.get("controller", self.controller),
            encounters=kwargs.get("encounters", self.encounters),
            geometry=self.geometry,
            exploration=self.exploration,
            sources=kwargs.get("sources", self.sources),
            monster=reference,
        )

    def test_native_birth_key_gate_all_exits_and_four_scoped_formations_survive_compilation(
        self,
    ):
        config = self.compile()
        self.assertEqual(config["route"]["key"], "quest-map-887-23621-4029")
        self.assertEqual(config["route"]["criterion"], "")
        self.assertEqual(config["route"]["native_template_id"], -1)
        self.assertEqual(config["topology"]["policy"], "owned-story-controller-v1")
        self.assertEqual(len(config["topology"]["exploration_geometry"]["cells"]), 911)
        self.assertEqual(
            [len(r["cells"]) for r in config["topology"]["rooms"]], [78, 64, 132, 74]
        )
        self.assertEqual(
            [r["requires"] for r in config["topology"]["rooms"]],
            [[], ["room1-gate"], ["puzzle-second-lever"], ["boss-intro-done"]],
        )
        self.assertEqual(
            {
                (r["source_id"], r["destination_id"])
                for r in config["topology"]["native_story_exits"]
            },
            {(23582, 2074), (23582, 2002), (23614, 2075), (23614, 2003)},
        )
        self.assertEqual(config["topology"]["physical_exit_objects"], [])
        self.assertEqual(config["topology"]["doors"], [])
        self.assertEqual(
            config["topology"]["owned_story_controller"]["trap_cycle"],
            self.controller["trap_cycle"],
        )
        self.assertFalse(config["compiled_plan"]["official"])
        self.assertEqual(
            [
                [(m["ref_id"], m["count"]) for m in room["monsters"]]
                for room in config["compiled_plan"]["rooms"]
            ],
            [[(3236, 2)], [(3236, 1), (3237, 1)], [(3235, 1), (3237, 1)], [(3234, 1)]],
        )
        native = dict(map_id=887, x=0, y=0, z=0)
        with patch.object(
            dungeon_runtime, "configuration_for_instance", return_value=({}, config)
        ):
            self.assertEqual(
                dungeon_runtime.entry_destination(None, dict(instance_id=99), native),
                native,
            )

    def test_cire_room_defeat_terminal_compiles_without_promoting_it_to_victory(self):
        root = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server/maps/owned_story_profiles"
        )
        manifest = json.loads((root / "ereboria-cire-1366.instance.json").read_text())
        controller = json.loads((root / manifest["controller_file"]).read_text())
        encounters = json.loads((root / manifest["encounters_file"]).read_text())
        exploration = json.loads((root / manifest["exploration_file"]).read_text())
        compiled = compile_story(
            manifest,
            controller=controller,
            encounters=encounters,
            geometry=published_geometry(1366),
            exploration=exploration,
            sources={
                (row["map_id"], row["id"]): row for row in generic_transports._CATALOG
            },
            monster=reference,
        )
        story = compiled["topology"]["owned_story_controller"]
        credit = [
            (step["kind"], step["reference"], effect["objective_id"])
            for step in story["steps"]
            for effect in step["effects"]
            if effect["kind"] == "quest_objective"
        ]
        self.assertEqual(compiled["route"]["key"], "quest-map-1366-33814-4558")
        self.assertTrue(story["enforce_native_entry_criterion"])
        self.assertEqual(
            [
                (row["ref_id"], row["count"])
                for row in compiled["compiled_plan"]["rooms"][0]["monsters"]
            ],
            [(5357, 1)],
        )
        self.assertEqual(credit, [("room_defeat", 1, 10539)])
        self.assertEqual(
            story["defeat_qualification"][0]["original_monster_reference"], 5357
        )
        self.assertEqual(
            story["defeat_qualification"][0]["native_effect_references"],
            controller["defeat_qualification"][0]["native_effect_references"],
        )

    def test_native_payment_mismatch_missing_victory_unknown_gate_and_paid_exit_reject(
        self,
    ):
        for case in ("payment", "criterion", "producer", "gate", "exit", "source_hash"):
            manifest, controller, encounters, sources = map(
                deepcopy,
                (self.manifest, self.controller, self.encounters, self.sources),
            )
            if case == "source_hash":
                controller["native_sources"]["sha256"] = "0" * 64
            elif case == "payment":
                manifest["native_entry_payment"]["quantity"] = 0
            elif case == "criterion":
                manifest["native_entry_criterion"] = "True"
            elif case == "producer":
                # Last room has no authentic room-victory producer.
                for step in controller["steps"]:
                    if step["kind"] == "room_victory" and step["reference"] == 4:
                        step["kind"] = "interactive"
            elif case == "gate":
                encounters["rooms"][-1]["requires"] = ["invented-unbound-step"]
            else:
                sources[(887, 23582)]["destinations"][0]["cyX"] = 1
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.compile(
                    manifest=manifest,
                    controller=controller,
                    encounters=encounters,
                    sources=sources,
                )

    def test_temple_718_safe_course_joins_actual_story_receipt_once(self):
        root = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server/maps/owned_story_profiles"
        )
        manifest = json.loads((root / "wild-temple-718.instance.json").read_text())
        controller = json.loads((root / manifest["controller_file"]).read_text())
        encounters = json.loads((root / manifest["encounters_file"]).read_text())
        exploration = json.loads((root / manifest["exploration_file"]).read_text())
        sidecar = json.loads((root / "wild-temple-718.trials.json").read_text())
        compiled = compile_story(
            manifest,
            controller=controller,
            encounters=encounters,
            geometry=published_geometry(718),
            exploration=exploration,
            sources={
                (row["map_id"], row["id"]): row for row in generic_transports._CATALOG
            },
            monster=reference,
            trial_sidecar=sidecar,
        )
        selected = compiled["topology"]["owned_object_trials"]
        story = compiled["topology"]["owned_story_controller"]
        trial = selected["trials"][0]
        self.assertEqual(
            (selected["map_id"], trial["id"], trial["hazard_zone_ids"]),
            (718, "water-safe-floor", [20619]),
        )
        self.assertEqual(
            [
                (monster["ref_id"], monster["count"])
                for monster in compiled["compiled_plan"]["rooms"][0]["monsters"]
            ],
            [(2798, 1), (2799, 1)],
        )

        program = trial["program"]
        edges = {}
        for origin, target in program["edges"]:
            edges.setdefault(tuple(origin), []).append(tuple(target))
        hazards = {tuple(cell) for cell in program["hazard_cells"]}
        start = tuple(program["start"])
        exits = {tuple(cell) for cell in program["exit_cells"]}
        pending = [(start, [list(start)])]
        seen = {start}
        path = None
        while pending:
            position, route = pending.pop(0)
            if position in exits:
                path = route
                break
            for target in edges.get(position, ()):
                if target not in seen and target not in hazards:
                    seen.add(target)
                    pending.append((target, route + [list(target)]))
        self.assertIsNotNone(
            path, "actual reviewed floor has no hazard-free route to its exit"
        )

        hazard_pending = [(start, [list(start)])]
        hazard_seen = {start}
        hazard_path = None
        while hazard_pending:
            position, route = hazard_pending.pop(0)
            for target in edges.get(position, ()):
                if target in hazards:
                    hazard_path = route + [list(target)]
                    break
                if target not in hazard_seen:
                    hazard_seen.add(target)
                    hazard_pending.append((target, route + [list(target)]))
            if hazard_path is not None:
                break
        self.assertIsNotNone(
            hazard_path, "actual floor has no reachable native hazard cell"
        )

        state = owned_object_trials.initial_state(selected)
        early = owned_object_trials.reduce(
            selected,
            state,
            {"kind": "movement", "cells": path},
            completed_story_steps=(),
        )
        self.assertFalse(early["changed"])
        self.assertEqual(early["state"], state)
        self.assertEqual(early["effects"], [])
        failed = owned_object_trials.reduce(
            selected,
            state,
            {"kind": "movement", "cells": hazard_path},
            completed_story_steps={"temple-entered"},
        )
        self.assertEqual(
            failed["state"]["trials"][trial["id"]]["program"]["stage"], "failed"
        )
        self.assertIn({"kind": "relocate", "position": [5, 11, 0]}, failed["effects"])
        self.assertFalse(
            any(effect.get("kind") == "story_event" for effect in failed["effects"])
        )
        accepted = owned_object_trials.reduce(
            selected,
            failed["state"],
            {"kind": "movement", "cells": path},
            completed_story_steps={"temple-entered"},
        )
        self.assertTrue(accepted["changed"])
        self.assertEqual(
            accepted["state"]["trials"][trial["id"]]["program"]["stage"], "success"
        )
        self.assertIn({"kind": "story_event", "reference": 71801}, accepted["effects"])
        joined = owned_story_controller.plan(
            story, {"temple-entered"}, kind="trial_success", reference=71801
        )
        self.assertEqual(joined["id"], "water-safe-floor-crossed")
        self.assertIsNone(
            owned_story_controller.plan(
                story,
                {"temple-entered", joined["id"]},
                kind="trial_success",
                reference=71801,
            )
        )
