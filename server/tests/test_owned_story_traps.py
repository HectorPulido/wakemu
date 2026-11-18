"""Native baseline hazards cycle deterministically without fake progress."""

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_story_traps as traps
from wakfu_server import owned_story_controller
from wakfu_server import dungeon_runtime_config


class StoryTrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = (
            Path(__file__).parents[1]
            / "wakfu_server/maps/owned_story_profiles/astrub-temple-887-hazards.json"
        )
        cls.document = json.loads(path.read_text())

    def test_native_baseline_alternates_and_reconnect_has_no_timer_drift(self):
        first = traps.clock(self.document, 1000, 1000)
        second = traps.clock(self.document, 1000, 7000)
        third = traps.clock(self.document, 1000, 13000)
        self.assertEqual(len(first["state_effects"]), 29)
        for tile, before, inverse, restored in zip(
            self.document["tiles"],
            first["state_effects"],
            second["state_effects"],
            third["state_effects"],
        ):
            self.assertEqual(before["state"], tile["initial_state"])
            self.assertEqual(inverse["state"], 1 - before["state"])
            self.assertEqual(restored["state"], before["state"])
            self.assertFalse(before["blocks_movement"])
            self.assertFalse(before["usable"])
        reconnected = traps.clock(self.document, 1000, 7555)
        self.assertEqual(reconnected["state_effects"], second["state_effects"])
        self.assertEqual(reconnected["next_transition_ms"], 13000)

    def test_missing_timing_duplicate_tiles_or_reset_on_spikes_are_rejected(self):
        for mutation in ("phase_ms", "duplicates", "reset"):
            document = deepcopy(self.document)
            if mutation == "phase_ms":
                del document["phase_ms"]
            elif mutation == "duplicates":
                document["tiles"].append(deepcopy(document["tiles"][0]))
            else:
                document["reset_position"] = document["tiles"][0]["position"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                traps.policy(document)

    def test_all_hazards_cannot_be_disabled_and_bool_time_is_not_a_clock(self):
        document = deepcopy(self.document)
        for tile in document["tiles"]:
            tile["initial_state"] = 0
        with self.assertRaises(ValueError):
            traps.policy(document)
        for now in (-1, True, 1000.0):
            with self.subTest(now=now), self.assertRaises(ValueError):
                traps.clock(self.document, 0, now)

    def test_readonly_missing_clock_never_initializes_or_acquires_owner_locks(self):
        story = dict(
            map_id=887, trap_cycle=self.document, steps=[dict(id="artifact-scene-done")]
        )
        owner = dict(id=7, instance_id=99, x=-15, y=-25, z=0)
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        with patch.object(
            owned_story_controller,
            "_scope",
            return_value=(story, {"artifact-scene-done"}),
        ) as scope, patch.object(traps.storage, "record_event") as record:
            result = traps.projection(
                db,
                "store",
                owner,
                dict(topology=dict(owned_story_controller=story)),
                7000,
                initialize=False,
            )
        self.assertFalse(result["active"])
        scope.assert_called_once_with(
            db, "store", owner, check_position=False, lock=False
        )
        record.assert_not_called()
        self.assertTrue(
            all(
                call.args[0].startswith("SELECT ") for call in db.execute.call_args_list
            )
        )

    def test_readonly_existing_clock_projects_same_phase_without_reinitializing(self):
        story = dict(
            map_id=887, trap_cycle=self.document, steps=[dict(id="artifact-scene-done")]
        )
        owner = dict(id=7, instance_id=99, x=-15, y=-25, z=0)
        payload = dict(
            schema=traps.SCHEMA,
            owner=7,
            instance_id=99,
            profile_sha256=owned_story_controller._digest(story),
            epoch_ms=1000,
        )
        db = Mock()
        db.execute.return_value.fetchone.return_value = dict(payload=payload)
        with patch.object(
            owned_story_controller,
            "_scope",
            return_value=(story, {"artifact-scene-done"}),
        ) as scope, patch.object(traps.storage, "record_event") as record:
            result = traps.projection(
                db,
                "store",
                owner,
                dict(topology=dict(owned_story_controller=story)),
                7555,
                initialize=False,
            )
        self.assertTrue(result["active"])
        self.assertEqual(result["phase"], 1)
        self.assertEqual(result["next_transition_ms"], 13000)
        scope.assert_called_once_with(
            db, "store", owner, check_position=False, lock=False
        )
        record.assert_not_called()

    def test_readonly_projection_ignores_stale_xyz_but_mutation_keeps_position_guard(
        self,
    ):
        story = json.loads(
            (
                Path(__file__).parents[1]
                / "wakfu_server/maps/owned_story_profiles/astrub-temple-887.configuration.json"
            ).read_text()
        )["topology"]["owned_story_controller"]
        configuration = dict(topology=dict(owned_story_controller=story))
        owner = dict(
            id=7,
            account_id=19,
            instance_id=99,
            map_id=887,
            x=-15,
            y=-25,
            z=0,
        )
        authoritative = dict(owner, x=-14)
        digest = owned_story_controller._digest(story)
        epoch_key = f'owned-story-traps:{story["trap_cycle"]["id"]}:99:epoch'
        epoch_payload = dict(
            schema=traps.SCHEMA,
            owner=7,
            instance_id=99,
            profile_sha256=digest,
            epoch_ms=1000,
        )
        step_payload = dict(
            schema=owned_story_controller.SCHEMA,
            profile_sha256=digest,
            owner=7,
            instance_id=99,
            step="artifact-scene-done",
        )

        class ProjectionDB:
            def execute(self, statement, params=()):
                cursor = Mock()
                if (
                    "FROM dungeon_instances i JOIN dungeon_instance_members"
                    in statement
                ):
                    cursor.fetchone.return_value = dict(
                        context_route_key="reviewed-trap-route",
                        context_policy_version=1,
                        start_map_id=887,
                    )
                elif "SELECT character_id FROM dungeon_instance_members" in statement:
                    cursor.fetchall.return_value = [dict(character_id=7)]
                elif "SELECT map_id,instance_id FROM characters" in statement:
                    cursor.fetchone.return_value = dict(map_id=887, instance_id=99)
                elif "left(event_key,%s)=%s" in statement:
                    cursor.fetchall.return_value = [
                        dict(event_key="story-step", payload=step_payload)
                    ]
                elif params == (7, epoch_key):
                    cursor.fetchone.return_value = dict(payload=epoch_payload)
                else:
                    raise AssertionError(
                        f"Unexpected SQL in projection fixture: {statement}"
                    )
                return cursor

        store = Mock()
        store.character.return_value = authoritative
        db = ProjectionDB()
        with patch.object(
            dungeon_runtime_config,
            "pinned_configuration",
            return_value=configuration,
        ):
            readonly = traps.projection(
                db, store, owner, configuration, 7555, initialize=False
            )
            self.assertTrue(readonly["active"])
            self.assertEqual(readonly["phase"], 1)
            with self.assertRaisesRegex(ValueError, "position changed"):
                traps.projection(db, store, owner, configuration, 7555)

            executor = Mock()
            with self.assertRaisesRegex(ValueError, "position changed"):
                traps.on_landing(
                    db,
                    store,
                    owner,
                    configuration,
                    movement_token="movement-17",
                    apply_effects=executor,
                    now_ms=7555,
                )
            executor.assert_not_called()

    def _landing(self, *, old=None, executor=None):
        db, store = Mock(), object()
        db.execute.return_value.fetchone.return_value = old
        state = dict(
            active=True,
            hazard_object=23443,
            reset=dict(position=[-15, -25, 0], due_ms=2600),
        )
        owner = dict(id=7, instance_id=99)
        with patch.object(traps, "projection", return_value=state), patch.object(
            traps.storage, "record_event", return_value=True
        ) as record:
            result = traps.on_landing(
                db,
                store,
                owner,
                {},
                movement_token="actual-movement:17",
                apply_effects=executor or Mock(return_value=[(12238, b"native")]),
                now_ms=1000,
            )
        return result, record

    def test_landing_records_only_after_native_executor_and_replay_is_inert(self):
        result, record = self._landing()
        self.assertTrue(result["applied"])
        record.assert_called_once()
        replay, record = self._landing(old=dict(payload={}))
        self.assertFalse(replay["applied"])
        record.assert_not_called()

    def test_native_reset_failure_never_burns_the_landing_receipt(self):
        executor = Mock(side_effect=ValueError("position registry rejected"))
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        state = dict(
            active=True, hazard_object=23443, reset=dict(position=[-15, -25, 0])
        )
        with patch.object(traps, "projection", return_value=state), patch.object(
            traps.storage, "record_event"
        ) as record:
            with self.assertRaisesRegex(ValueError, "position registry rejected"):
                traps.on_landing(
                    db,
                    "store",
                    {"id": 7, "instance_id": 99},
                    {},
                    movement_token="actual-movement:17",
                    apply_effects=executor,
                    now_ms=1000,
                )
            record.assert_not_called()

    def test_scheduler_phase_can_raise_hazard_under_a_stationary_owner(self):
        state = dict(
            active=True,
            phase=3,
            hazard_object=23443,
            reset=dict(position=[-15, -25, 0], due_ms=2600),
        )
        db, executor = Mock(), Mock(return_value=[(12238, b"native-fall")])
        db.execute.return_value.fetchone.side_effect = [None, dict(payload={})]
        with patch.object(traps, "projection", return_value=state), patch.object(
            traps.storage, "record_event", return_value=True
        ) as record:
            result = traps.on_tick(
                db,
                "store",
                {"id": 7, "instance_id": 99},
                {},
                apply_effects=executor,
                now_ms=1000,
            )
            replay = traps.on_tick(
                db,
                "store",
                {"id": 7, "instance_id": 99},
                {},
                apply_effects=executor,
                now_ms=1001,
            )
        self.assertTrue(result["applied"])
        self.assertFalse(replay["applied"])
        executor.assert_called_once()
        record.assert_called_once()


if __name__ == "__main__":
    unittest.main()
