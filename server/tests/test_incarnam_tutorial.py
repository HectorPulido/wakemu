"""Incarnam mission transitions follow the observed sequence and stay durable."""

import unittest
import struct
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from copy import deepcopy
from wakfu_server.achievements import incarnam_tutorial as tutorial
from wakfu_server.achievements import incarnam_resources


def empty():
    return {
        "variables": {},
        "tracking": [],
        "recent": [],
        "completion_dates": {},
        "running": [],
        "completed": [],
        "objectives": [],
    }


class TutorialTest(unittest.TestCase):
    def test_reconnect_ready_does_not_rearm_the_arrival_cinematic(self):
        from wakfu_server.intro_cinematic import private_instance_id

        character = {"id": 7, "map_id": 1361, "instance_id": private_instance_id(7)}
        for identity, _, _ in tutorial.STAGES:
            state = {"running": [identity]}
            self.assertTrue(
                tutorial.is_resumed_scene_ready(character, state, 21800, None)
            )
            self.assertFalse(
                tutorial.is_resumed_scene_ready(character, state, 22519, None)
            )
            self.assertFalse(
                tutorial.is_resumed_scene_ready(character, state, 21800, (7, 21800))
            )
        self.assertFalse(
            tutorial.is_resumed_scene_ready(character, {"running": []}, 21800, None)
        )
        self.assertFalse(
            tutorial.is_resumed_scene_ready(
                {**character, "instance_id": private_instance_id(8)},
                {"running": [5135]},
                21800,
                None,
            )
        )
        from wakfu_server.application.session_world import WorldSessionMixin
        from wakfu_server.application.dispatch_result import DispatchResult

        session = WorldSessionMixin()
        session.state = SimpleNamespace(
            body=struct.pack(">i", 21800),
            character=character,
            connection=SimpleNamespace(),
        )
        session.runtime = SimpleNamespace(STORE=Mock(), send=Mock())
        session.runtime.STORE.connection.return_value.__enter__ = Mock(
            return_value=object()
        )
        session.runtime.STORE.connection.return_value.__exit__ = Mock(
            return_value=False
        )
        with patch.object(
            tutorial.storage, "load_locked", return_value={"running": [5135]}
        ):
            self.assertIs(session.handle_world_loaded(), DispatchResult.FALLTHROUGH)
        session.runtime.send.assert_not_called()
        self.assertFalse(hasattr(session.state.connection, "pending_incarnam_arrival"))

    def test_arrival_camera_loads_observed_scene_then_returns_to_spawn(self):
        for callback, point in ((22519, (434, 362, 1)), (22521, (0, 0, 0))):
            packets = tutorial.cinematic_camera_travel(7, callback)
            self.assertEqual([kind for kind, _ in packets], [13259, 12318])
            self.assertEqual(struct.unpack(">qiihBB", packets[0][1]), (7, *point, 0, 0))
            self.assertEqual(struct.unpack(">ii", packets[1][1]), point[:2])
        with self.assertRaises(ValueError):
            tutorial.cinematic_camera_travel(7, 21800)

    def setUp(self):
        self.state = empty()
        self.db = Mock()
        self.store = SimpleNamespace(
            now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        self.character = {"id": 7, "map_id": 1361, "instance_id": 0}
        self.defs = {
            q: {
                "d": q,
                "native_class": "aJM",
                "aqb": False,
                "cjI": "",
                "cjU": 0,
                "getDuration": 0,
                "cjJ": [{"d": o}],
            }
            for q, o, _ in tutorial.STAGES
        }
        self.db.execute.side_effect = lambda sql, args: Mock(
            fetchone=Mock(return_value={"data": {"native": self.defs[args[0]]}})
        )

        def save(db, ident, state):
            self.state = state

        def advance(state, definition, objective, **kwargs):
            state = deepcopy(state)
            identity = definition["d"]
            state["running"].remove(identity)
            state["completed"].append(identity)
            state["objectives"].append(objective)
            state["tracking"].remove(identity)
            return state, [], [objective], [identity]

        def settle(db, store, character, before, planned, definitions, links, **kwargs):
            self.state = planned[0]
            return {"packets": [(13832, b"objective")]}

        for name, target, value in (
            ("load", "storage.load_locked", lambda *a: self.state),
            ("save", "storage.store", save),
            ("receipt", "storage.record_event", lambda *a: True),
            ("advance", "mission_progress.advance_objective", advance),
            ("settle", "mission_dependencies.settle", settle),
        ):
            obj, attr = target.split(".")
            p = patch.object(getattr(tutorial, obj), attr, side_effect=value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(incarnam_resources, "give_seed", return_value=[])
        p.start()
        self.addCleanup(p.stop)

    def test_start_and_all_authorized_events_keep_chain_and_tracking(self):
        self.assertEqual(
            tutorial.enter(self.db, self.store, self.character, previous_map=527), []
        )
        self.assertTrue(
            tutorial.enter(self.db, self.store, self.character, previous_map=1465)
        )
        self.assertEqual(self.state["running"], [5135])
        self.assertEqual(
            tutorial.enter(self.db, self.store, self.character, previous_map=1465), []
        )
        for index, (identity, objective, event) in enumerate(tutorial.STAGES[:-1]):
            self.assertTrue(
                tutorial.settle(
                    self.db, self.store, self.character, event=event, token="1"
                )
            )
            self.assertIn(objective, self.state["objectives"])
            self.assertEqual(self.state["running"], [tutorial.STAGES[index + 1][0]])
            self.assertEqual(self.state["tracking"], self.state["running"])
            self.assertEqual(
                tutorial.settle(
                    self.db, self.store, self.character, event=event, token="1"
                ),
                [],
            )
        self.assertNotIn(10568, self.state["objectives"])

    def test_wrong_map_and_out_of_order_events_do_not_progress(self):
        tutorial.enter(self.db, self.store, self.character, previous_map=1465)
        self.assertEqual(
            tutorial.settle(
                self.db, self.store, self.character, event="wood_harvest", token="1"
            ),
            [],
        )
        self.assertEqual(
            tutorial.settle(
                self.db,
                self.store,
                {**self.character, "map_id": 1385},
                event="first_wodent_victory",
                token="1",
            ),
            [],
        )
        self.assertEqual(self.state["completed"], [])
        with self.assertRaises(ValueError):
            tutorial.settle(
                self.db, self.store, self.character, event="forged", token="1"
            )

    def test_one_time_presentations_have_durable_distinct_receipts(self):
        seen = set()

        def record(db, actor, key, payload):
            if (actor, key) in seen:
                return False
            seen.add((actor, key))
            return True

        tutorial.storage.record_event.side_effect = record
        for event in (22524, 22354):
            self.assertTrue(tutorial.claim_presentation(self.db, 7, event))
            self.assertFalse(tutorial.claim_presentation(self.db, 7, event))
            self.assertTrue(tutorial.claim_presentation(self.db, 8, event))
        with self.assertRaises(ValueError):
            tutorial.claim_presentation(self.db, 7, 22359)

    def test_reconnect_visual_state_uses_current_stage(self):
        for quest, expected in (
            (5135, 10),
            (5136, 20),
            (5137, 30),
            (5138, 40),
            (5139, 50),
        ):
            state = empty()
            state["running"] = [quest]
            start, restore = tutorial.initial_packets(state)
            self.assertEqual(struct.unpack(">BiiB", start[1]), (0, 21800, 2500, 0))
            self.assertEqual(
                struct.unpack(">BiiBq", restore[1]), (0, 22505, 2500, 1, expected)
            )
        state = empty()
        state["running"] = [5136]
        start, restore, shortcut = tutorial.initial_packets(
            state, planting_guide_seen=True
        )
        self.assertEqual(struct.unpack(">BiiBq", restore[1]), (0, 22505, 2500, 1, 25))
        self.assertEqual(struct.unpack(">BiiB", shortcut[1]), (0, 22566, 2500, 0))

    def test_planting_guide_requires_owned_scene_and_active_mission(self):
        from wakfu_server.intro_cinematic import private_instance_id

        self.character.update(instance_id=private_instance_id(7), x=12, y=-28, z=-13)
        self.store.connection = Mock()
        self.store.connection.return_value.__enter__ = Mock(return_value=self.db)
        self.store.connection.return_value.__exit__ = Mock(return_value=False)
        self.store.lock_character = Mock()
        self.store.character = Mock(return_value=self.character)
        body = struct.pack(">qHH", 34658, 5, 0)
        self.assertFalse(tutorial.blocked_path(self.store, 1, 1, self.character, body))
        self.state["running"] = [5136]
        with patch.object(tutorial, "planting_guide_seen", return_value=False):
            self.assertTrue(
                tutorial.blocked_path(self.store, 1, 1, self.character, body)
            )
        self.assertTrue(tutorial.finish_planting_guide(self.store, 1, 1, 7))
        tutorial.storage.record_event.assert_called_with(
            self.db,
            7,
            "incarnam-planting-guide:finished",
            {"kind": "incarnam_planting_guide_finished"},
        )
        with patch.object(tutorial, "planting_guide_seen", return_value=True):
            self.assertFalse(
                tutorial.blocked_path(self.store, 1, 1, self.character, body)
            )
        self.character["x"] = 100
        with self.assertRaises(ValueError):
            tutorial.blocked_path(self.store, 1, 1, self.character, body)


if __name__ == "__main__":
    unittest.main()
