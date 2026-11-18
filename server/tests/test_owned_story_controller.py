"""Ordered owned-room mechanics preserve real producers and once-only flags."""

from copy import deepcopy
import json
from datetime import datetime, timezone
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import wakfu_server
from wakfu_server import owned_story_controller as controller

PROFILE = (
    Path(__file__).parents[1]
    / "wakfu_server/maps/owned_story_profiles/astrub-temple-887.json"
)


class OwnedStoryPlanningTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(PROFILE.read_text())
        self.configuration = dict(topology=dict(owned_story_controller=self.profile))

    def test_physical_entry_is_independent_of_quests_but_story_admission_is_not(self):
        from wakfu_server import companions, dungeon_instances, dungeon_runtime_config
        from wakfu_server import owned_companion_rescue
        from wakfu_server.achievements import owned_quest_encounters

        cases = (
            ("questless", [], [], False, False),
            ("active-main", [2166], [], False, True),
            ("stale-running-and-completed", [2166], [2166], False, False),
            ("completed-main-only", [], [2166], False, False),
            ("followup-running", [2170], [2166], True, False),
            ("followup-completed", [], [2166, 2170], True, False),
        )
        for name, running, completed, expects_admission, expects_advance in cases:
            with self.subTest(case=name):
                character = dict(id=7, account_id=3, map_id=887, instance_id=99)
                db = Mock()
                db.execute.return_value.fetchone.return_value = dict(id=7, account_id=3)
                store = SimpleNamespace(character=Mock(return_value=character))
                session = dict(instance_id=99, context_policy_version=1, members=[7])
                state = dict(completed=completed, running=running)
                advance = Mock()
                admit = Mock(return_value=[])
                with (
                    patch.object(
                        dungeon_instances, "canonical_context_key", return_value="route"
                    ),
                    patch.object(
                        dungeon_runtime_config, "pinned_configuration", return_value={}
                    ),
                    patch.object(companions, "controlled_count", return_value=0),
                    patch.object(controller, "policy", return_value=self.profile),
                    patch.object(
                        controller, "_scope", return_value=(self.profile, set())
                    ),
                    patch.object(controller.storage, "load_locked", return_value=state),
                    patch.object(owned_quest_encounters, "_advance", advance),
                    patch.object(owned_companion_rescue, "admit", admit),
                ):
                    controller.initialize(db, session, dict(route="route"), store=store)
                if expects_advance:
                    advance.assert_called_once()
                    self.assertEqual(advance.call_args.args[4], 4288)
                else:
                    advance.assert_not_called()
                if expects_admission:
                    admit.assert_called_once()
                else:
                    admit.assert_not_called()
                self.assertEqual(
                    session["owned_story_controller"],
                    dict(owner=7, policy=self.profile["id"]),
                )

    def test_cave_world_ready_records_the_exact_native_instance_entrance(self):
        from wakfu_server import dungeon_runtime_config, owned_story_mechanics

        config_path = (
            Path(__file__).parents[1]
            / "wakfu_server/maps/owned_story_profiles/zinit-cult-cave-987.configuration.json"
        )
        configuration = json.loads(config_path.read_text())
        selected = configuration["topology"]["owned_story_controller"]
        route = configuration["route"]
        admitted = dict(
            context_route_key=route["key"],
            context_policy_version=configuration["version"],
            entry_map_id=route["entry_map_id"],
            entry_object_id=route["entry_object_id"],
            entry_destination_id=route["destination_id"],
        )
        character = dict(id=369, account_id=12, map_id=987, instance_id=919)
        store = object()

        def invoke(entry):
            db = Mock()
            db.execute.return_value.fetchone.return_value = entry
            settle = Mock(return_value={"applied": True, "packets": []})
            with patch.object(
                controller, "_scope", return_value=(selected, set())
            ), patch.object(
                dungeon_runtime_config,
                "pinned_configuration",
                return_value=configuration,
            ), patch.object(
                owned_story_mechanics, "executor", return_value=Mock()
            ), patch.object(
                controller, "_settle", settle
            ):
                result = controller.on_world_ready(db, store, character)
            return result, settle

        result, settle = invoke(admitted)
        self.assertEqual(result, {"applied": True, "packets": []})
        evidence = settle.call_args.kwargs["evidence"]
        self.assertEqual(
            (
                evidence["route_key"],
                evidence["entry_map_id"],
                evidence["source_id"],
                evidence["destination_id"],
            ),
            ("quest-map-987-25392-2233", 986, 25392, 2233),
        )

        db = Mock()
        db.execute.return_value.fetchone.return_value = dict(
            admitted, entry_object_id=25393
        )
        with patch.object(
            controller, "_scope", return_value=(selected, set())
        ), patch.object(
            dungeon_runtime_config,
            "pinned_configuration",
            return_value=configuration,
        ), patch.object(
            owned_story_mechanics, "executor", return_value=Mock()
        ), patch.object(
            controller, "_settle"
        ) as rejected_settle:
            with self.assertRaisesRegex(ValueError, "exact native entrance"):
                controller.on_world_ready(db, store, character)
        rejected_settle.assert_not_called()

    def test_null_admission_objective_is_valid_and_never_fakes_quest_5305(self):
        from wakfu_server import companions, dungeon_instances, dungeon_runtime_config
        from wakfu_server import owned_companion_rescue
        from wakfu_server.achievements import owned_quest_encounters

        profile = deepcopy(self.profile)
        profile["admission"] = dict(
            quest_id=5305, objective_id=None, continuation_quest_id=5306
        )
        configuration = dict(topology=dict(owned_story_controller=profile))
        self.assertIs(controller.policy(configuration), profile)
        character = dict(id=7, account_id=3, map_id=887, instance_id=99)
        db = Mock()
        db.execute.return_value.fetchone.return_value = dict(id=7, account_id=3)
        store = SimpleNamespace(character=Mock(return_value=character))
        session = dict(instance_id=99, context_policy_version=1, members=[7])
        state = dict(running=[5305], completed=[], objectives=[])
        advance = Mock()
        with (
            patch.object(
                dungeon_instances, "canonical_context_key", return_value="route"
            ),
            patch.object(
                dungeon_runtime_config,
                "pinned_configuration",
                return_value=configuration,
            ),
            patch.object(companions, "controlled_count", return_value=0),
            patch.object(controller, "_scope", return_value=(profile, set())),
            patch.object(controller.storage, "load_locked", return_value=state),
            patch.object(owned_quest_encounters, "_advance", advance),
            patch.object(owned_companion_rescue, "admit") as admit,
        ):
            controller.initialize(db, session, dict(route="route"), store=store)

        advance.assert_not_called()
        admit.assert_not_called()
        self.assertEqual(state["running"], [5305])
        self.assertEqual(state["completed"], [])
        self.assertEqual(state["objectives"], [])
        self.assertEqual(
            session["owned_story_controller"], dict(owner=7, policy=profile["id"])
        )

    def test_room_admission_accepts_native_room_actor_roles_and_rejects_malformed_roles(
        self,
    ):
        valid = deepcopy(self.profile)
        valid["steps"][0]["kind"] = "room_admission"
        valid["steps"][0]["effects"][0]["arguments"] = ["room_actor:1:0"]
        selected = controller.policy(dict(topology=dict(owned_story_controller=valid)))
        self.assertIs(selected, valid)
        self.assertEqual(
            controller.plan(valid, set(), kind="room_admission", reference=887),
            valid["steps"][0],
        )

        for value in (
            "room_actor:0:0",
            "room_actor:1:-1",
            "room_actor:01:0",
            "room_actor:1:00",
            "room_actor:1",
            "room_actor:-2:0",
        ):
            malformed = deepcopy(valid)
            malformed["steps"][0]["effects"][0]["arguments"] = [value]
            with self.subTest(actor_role=value), self.assertRaisesRegex(
                ValueError, "native identity"
            ):
                controller.policy(dict(topology=dict(owned_story_controller=malformed)))

    def test_admission_quest_and_continuation_ids_stay_positive_when_objective_is_null(
        self,
    ):
        baseline = deepcopy(self.profile)
        baseline["admission"]["objective_id"] = None
        self.assertIs(
            controller.policy(dict(topology=dict(owned_story_controller=baseline))),
            baseline,
        )
        for field in ("quest_id", "continuation_quest_id"):
            for invalid in (0, -1, True):
                malformed = deepcopy(baseline)
                malformed["admission"][field] = invalid
                with self.subTest(field=field, value=invalid), self.assertRaisesRegex(
                    ValueError, "admission"
                ):
                    controller.policy(
                        dict(topology=dict(owned_story_controller=malformed))
                    )
        for invalid in (0, -1, True):
            malformed = deepcopy(baseline)
            malformed["admission"]["objective_id"] = invalid
            with self.subTest(
                field="objective_id", value=invalid
            ), self.assertRaisesRegex(ValueError, "admission"):
                controller.policy(dict(topology=dict(owned_story_controller=malformed)))

    def test_native_five_room_flow_uses_four_real_encounters_and_an_actual_puzzle(self):
        selected = controller.policy(self.configuration)
        self.assertIs(selected, self.profile)
        fights = [row for row in selected["steps"] if row["kind"] == "room_victory"]
        self.assertEqual([row["reference"] for row in fights], [1, 2, 3, 4])
        self.assertEqual(
            [row["id"] for row in fights],
            ["room1-victory", "room2-victory", "room4-victory", "boss-victory"],
        )
        self.assertTrue(
            any(row["id"] == "puzzle-second-lever" for row in selected["steps"])
        )
        artifact = next(
            row for row in selected["steps"] if row["id"] == "artifact-chest"
        )
        self.assertIn(dict(kind="native_loot", table_id=2437), artifact["effects"])

    def test_callbacks_chests_and_room_wins_cannot_skip_the_actual_order(self):
        for kind, reference in (
            ("interactive", 23399),
            ("room_victory", 4),
            ("scenario_complete", 2),
            ("interactive", 23583),
        ):
            self.assertIsNone(
                controller.plan(self.profile, set(), kind=kind, reference=reference)
            )
        state = set()
        for step in self.profile["steps"]:
            planned = controller.plan(
                self.profile, state, kind=step["kind"], reference=step["reference"]
            )
            self.assertEqual(planned, step)
            state.add(planned["id"])
            # Shared native callback2 is accepted only at its particular stage;
            # after completion it cannot replay that stage's effects.
            replay = controller.plan(
                self.profile, state, kind=step["kind"], reference=step["reference"]
            )
            self.assertNotEqual(replay, step)
        self.assertEqual(len(state), 17)

    def test_reconnect_projects_flags_without_replaying_loot_or_cinematics(self):
        done = {row["id"] for row in self.profile["steps"]}
        effects = controller.presentation_state(self.profile, done)
        self.assertTrue(effects)
        self.assertEqual({effect["kind"] for effect in effects}, {"element_state"})
        by_id = {effect["object_id"]: effect for effect in effects}
        self.assertFalse(by_id[23399]["usable"])
        self.assertEqual(by_id[23424]["state"], 0)
        self.assertFalse(by_id[23424]["blocks_movement"])

    def test_a_key_enables_the_native_gate_action_but_does_not_open_its_collision(self):
        steps = {"room1-victory", "room1-key"}
        enabled = {
            row["object_id"]: row
            for row in controller.presentation_state(self.profile, steps)
        }[23400]
        self.assertTrue(enabled["usable"])
        self.assertTrue(enabled["blocks_movement"])
        self.assertEqual(enabled["state"], 1)
        opened = {
            row["object_id"]: row
            for row in controller.presentation_state(
                self.profile, steps | {"room1-gate"}
            )
        }[23400]
        self.assertFalse(opened["blocks_movement"])
        self.assertEqual(opened["state"], 0)

    def test_foreign_receipts_forward_edges_and_duplicate_steps_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "another profile"):
            controller.plan(self.profile, {"foreign"}, kind="room_victory", reference=1)
        for mutation in ("forward", "duplicate", "visual_only"):
            malformed = deepcopy(self.configuration)
            steps = malformed["topology"]["owned_story_controller"]["steps"]
            if mutation == "forward":
                steps[0]["requires"] = ["boss-victory"]
            elif mutation == "duplicate":
                steps.append(deepcopy(steps[0]))
            else:
                effect = next(
                    effect
                    for step in steps
                    for effect in step["effects"]
                    if effect["kind"] == "element_state"
                )
                del effect["blocks_movement"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                controller.policy(malformed)

    def test_unavailable_effect_adapter_cannot_create_a_completion_receipt(self):
        record = Mock()
        with patch.object(controller.storage, "record_event", record):
            with self.assertRaisesRegex(ValueError, "native mechanic"):
                controller._settle(
                    None,
                    None,
                    dict(id=1, instance_id=22),
                    self.profile,
                    set(),
                    kind="room_victory",
                    reference=1,
                    evidence={},
                    apply_effects=None,
                )
        record.assert_not_called()

    def test_failed_native_mechanic_cannot_record_its_step(self):
        record = Mock()
        apply = Mock(side_effect=ValueError("native key payment rejected"))
        with patch.object(controller.storage, "record_event", record):
            with self.assertRaisesRegex(ValueError, "key payment"):
                controller._settle(
                    None,
                    None,
                    dict(id=1, instance_id=22),
                    self.profile,
                    set(),
                    kind="room_victory",
                    reference=1,
                    evidence={},
                    apply_effects=apply,
                )
        record.assert_not_called()

    def test_cinematic_callback_requires_owned_pending_marker_and_offered_scene_receipt(
        self,
    ):
        character = dict(id=1, instance_id=22)
        artifact_index = next(
            i
            for i, row in enumerate(self.profile["steps"])
            if row["id"] == "artifact-chest"
        )
        done = {row["id"] for row in self.profile["steps"][: artifact_index + 1]}
        with patch.object(controller, "_scope", return_value=(self.profile, done)):
            for marker in (None, (23, "artifact-scene-done"), (22, "boss-intro-done")):
                with self.subTest(marker=marker), self.assertRaisesRegex(
                    ValueError, "not pending"
                ):
                    controller.on_scene_complete(
                        None,
                        None,
                        character,
                        struct.pack(">i", 2),
                        pending_step=marker,
                        apply_effects=Mock(),
                    )
            apply = Mock(return_value=[(12344, b"native")])
            with patch.object(controller.storage, "record_event", return_value=True):
                result = controller.on_scene_complete(
                    None,
                    SimpleNamespace(now=lambda: datetime.now(timezone.utc)),
                    character,
                    struct.pack(">i", 2),
                    pending_step=(22, "artifact-scene-done"),
                    apply_effects=apply,
                )
        self.assertTrue(result["applied"])
        self.assertEqual(result["step"], "artifact-scene-done")

    def test_native_private_interaction_uses_exact_object_and_position(self):
        native = dict(
            id=23399, type="GenericActivableInteractiveElement", x=-4, y=-8, z=0
        )
        world = SimpleNamespace(objects=Mock(return_value=[native]))
        character = dict(id=1, instance_id=22, map_id=887, x=-4, y=-7, z=0)
        with patch.object(
            wakfu_server, "world_static", world, create=True
        ), patch.object(
            controller, "_scope", return_value=(self.profile, {"room1-victory"})
        ), patch.object(
            controller.storage, "record_event", return_value=True
        ):
            result = controller.interact(
                None,
                SimpleNamespace(now=lambda: datetime.now(timezone.utc)),
                character,
                struct.pack(">qHH", 23399, 0, 0),
                apply_effects=Mock(return_value=[]),
            )
            self.assertTrue(result["applied"])
            for body in (
                b"",
                struct.pack(">qHH", 23399, 1, 0),
                struct.pack(">qHH", 999, 0, 0),
            ):
                with self.subTest(body=body), self.assertRaises(ValueError):
                    controller.interact(
                        None, None, character, body, apply_effects=Mock()
                    )
            with self.assertRaisesRegex(ValueError, "range"):
                controller.interact(
                    None,
                    None,
                    dict(character, z=12),
                    struct.pack(">qHH", 23399, 0, 0),
                    apply_effects=Mock(),
                )


if __name__ == "__main__":
    unittest.main()
