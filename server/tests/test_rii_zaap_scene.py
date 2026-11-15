"""Captured native Rii Zaap interaction, hidden fact and scene callback."""

import copy
import struct
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from wakfu_server import rii_zaap_scene


def hidden_definition():
    return {
        "d": 5278,
        "native_class": "aJM",
        "aqb": True,
        "isVisible": False,
        "cjI": "",
        "cjU": 0,
        "getDuration": 0,
        "cjJ": [
            {
                "d": 10967,
                "native_class": "aJN",
                "ckb": True,
                "ckc": "",
                "cke": "",
                "ckd": [],
                "ckf": [],
            }
        ],
        "cjK": [],
    }


def state():
    return {
        "variables": {},
        "objectives": [],
        "running": [5160],
        "completed": [],
        "tracking": [5160],
        "recent": [],
        "completion_dates": {},
    }


class RiiZaapSceneTests(unittest.TestCase):
    def setUp(self):
        self.character = {
            "id": 7,
            "account_id": 2,
            "map_id": 1385,
            "instance_id": 0,
            "x": 2,
            "y": -11,
            "z": 1,
        }
        self.activation = struct.pack(">qHH", 34719, 5, 0)

    def test_recognizes_only_the_map_scoped_portal_element(self):
        self.assertTrue(
            rii_zaap_scene.handles_activation(self.character, self.activation)
        )
        self.assertFalse(
            rii_zaap_scene.handles_activation(
                {**self.character, "map_id": 527}, self.activation
            )
        )
        self.assertFalse(
            rii_zaap_scene.handles_activation(
                {**self.character, "instance_id": 99}, self.activation
            )
        )
        self.assertFalse(rii_zaap_scene.handles_activation(self.character, b"short"))

    def test_activation_requires_native_action_and_captured_approach_or_trigger(self):
        rii_zaap_scene._parse_activation(self.activation)
        for malformed in (
            struct.pack(">qHH", 34719, 4, 0),
            struct.pack(">qHH", 34719, 5, 1),
            self.activation[:-1],
        ):
            with self.subTest(packet=malformed), self.assertRaises(ValueError):
                rii_zaap_scene._parse_activation(malformed)

        for position in rii_zaap_scene.TRIGGER_CELLS:
            rii_zaap_scene._authorized_position(
                dict(self.character, x=position[0], y=position[1], z=position[2])
            )
        with self.assertRaisesRegex(ValueError, "trigger"):
            rii_zaap_scene._authorized_position(dict(self.character, y=-8))
        with self.assertRaisesRegex(ValueError, "trigger"):
            rii_zaap_scene._authorized_position(dict(self.character, map_id=527))

    def test_native_trigger_accepts_only_the_current_approved_crossing_route(self):
        endpoint = dict(self.character, x=4, y=-19, z=6)
        approved = frozenset({(6, -9, 1), (4, -15, 1), (4, -19, 6)})
        rii_zaap_scene._authorized_position(endpoint, approved_positions=approved)
        for invalid in (
            (),
            {(6, -9, 1), (4, -19, 6)},
            {(6, -9, 1), (4, -15, 1)},
            {(4, -19, 6), (4, -15, 2)},
            ((4, -19, 6), (4, -15, True)),
        ):
            with self.subTest(route=invalid), self.assertRaises(ValueError):
                rii_zaap_scene._authorized_position(
                    endpoint, approved_positions=invalid
                )
        with self.assertRaises(ValueError):
            rii_zaap_scene._authorized_position(
                dict(endpoint, map_id=527), approved_positions=approved
            )

    def test_departure_route_uses_installed_destination_coordinates(self):
        self.assertEqual(
            rii_zaap_scene.departure_route(),
            {
                "direction": 3,
                "destination": {
                    "map_id": 895,
                    "instance_id": 0,
                    "x": -8,
                    "y": -1,
                    "z": 18,
                },
            },
        )

    def test_login_packets_resume_only_pending_authenticated_scene(self):
        character = dict(self.character)
        starter = {
            "event_key": rii_zaap_scene.START_EVENT_KEY,
            "payload": rii_zaap_scene._start_payload(7),
        }

        class Events:
            rows = [starter]

            def execute(self, _sql, _params):
                return self

            def fetchall(self):
                return list(self.rows)

        db = Events()
        packets = rii_zaap_scene.login_packets(db, character)
        self.assertEqual([opcode for opcode, _body in packets], [13411, 12344])

        db.rows = [
            starter,
            {
                "event_key": rii_zaap_scene.CALLBACK_EVENT_KEY,
                "payload": {
                    "kind": "rii_zaap_scene_callback",
                    "character_id": 7,
                    "scenario_event": 22534,
                },
            },
        ]
        self.assertEqual(rii_zaap_scene.login_packets(db, character), ())
        self.assertEqual(
            rii_zaap_scene.login_packets(db, dict(character, map_id=527)), ()
        )

    def test_hidden_single_step_completes_without_starting_or_tracking_it(self):
        before = state()
        after, objectives, completed = rii_zaap_scene._complete_hidden_step(
            before, hidden_definition(), 1234
        )
        self.assertEqual(objectives, [10967])
        self.assertEqual(completed, [5278])
        self.assertEqual(after["objectives"], [10967])
        self.assertEqual(after["completed"], [5278])
        self.assertEqual(after["tracking"], [5160])
        self.assertEqual(after["running"], [5160])
        self.assertEqual(after["completion_dates"], {"5278": 1234})
        self.assertEqual(after["recent"], [{"id": 5278, "date_ms": 1234}])
        self.assertEqual(before, state())

    def test_hidden_step_has_no_unproven_parent_gate(self):
        before = state()
        before["running"] = []
        after, objectives, completed = rii_zaap_scene._complete_hidden_step(
            before, hidden_definition(), 1
        )
        self.assertEqual(objectives, [10967])
        self.assertEqual(completed, [5278])
        self.assertEqual(after["running"], [])

        partial = state()
        partial["objectives"] = [10967]
        with self.assertRaisesRegex(ValueError, "partially"):
            rii_zaap_scene._complete_hidden_step(partial, hidden_definition(), 1)

        visible = hidden_definition()
        visible["isVisible"] = True
        with self.assertRaisesRegex(ValueError, "(?i)hidden Rii portal quest"):
            rii_zaap_scene._complete_hidden_step(state(), visible, 1)

        rewarded = hidden_definition()
        rewarded["cjK"] = [{"d": 1}]
        with self.assertRaisesRegex(ValueError, "(?i)hidden Rii portal quest"):
            rii_zaap_scene._complete_hidden_step(state(), rewarded, 1)

    def _store_and_db(
        self, *, current=None, saved_state=None, starter=None, callback=None
    ):
        db = MagicMock()

        def query(sql, params=()):
            result = MagicMock()
            result.rowcount = 1
            if "native_quest_metadata_definitions" in sql:
                result.fetchone.return_value = {"data": {"native": hidden_definition()}}
            elif (
                "character_achievement_events" in sql
                and params
                and params[-1] == rii_zaap_scene.CALLBACK_EVENT_KEY
            ):
                result.fetchone.return_value = callback
            elif "character_achievement_events" in sql:
                result.fetchone.return_value = starter
            else:
                result.fetchone.return_value = None
            return result

        db.execute.side_effect = query
        store = MagicMock()
        store.connection.return_value.__enter__.return_value = db
        store.character.return_value = dict(
            self.character if current is None else current
        )
        store.now.return_value = datetime(2026, 11, 14, tzinfo=timezone.utc)
        return store, db

    def test_begin_authorizes_trigger_during_an_approved_in_flight_walk(self):
        endpoint = dict(self.character, x=4, y=-19, z=6)
        approved = frozenset({(6, -9, 1), (4, -15, 1), (4, -19, 6)})
        store, _ = self._store_and_db(current=endpoint)
        with patch(
            "wakfu_server.achievements.storage.load_locked", return_value=state()
        ), patch(
            "wakfu_server.achievements.storage.record_event", return_value=True
        ), patch(
            "wakfu_server.achievements.storage.store"
        ):
            result = rii_zaap_scene.begin(
                store,
                2,
                3,
                endpoint,
                self.activation,
                approved_positions=approved,
            )
        self.assertTrue(result["started"])
        self.assertEqual(
            tuple(result["character"][axis] for axis in ("x", "y", "z")),
            rii_zaap_scene.SCENE_POSITION,
        )

    def test_begin_commits_hidden_progress_once_then_starts_native_scene(self):
        store, db = self._store_and_db()
        before = state()
        with patch(
            "wakfu_server.achievements.storage.load_locked", return_value=before
        ), patch(
            "wakfu_server.achievements.storage.record_event", return_value=True
        ) as record, patch(
            "wakfu_server.achievements.storage.store"
        ) as persist:
            result = rii_zaap_scene.begin(store, 2, 3, self.character, self.activation)

        self.assertTrue(result["started"])
        self.assertEqual(
            [op for op, _ in result["packets"]],
            [13530, 13832, 13422, 13411, 12344],
        )
        self.assertEqual(result["character"]["x"], 3)
        self.assertEqual(result["character"]["y"], -18)
        self.assertEqual(result["character"]["z"], 4)
        self.assertEqual(
            struct.unpack(">qiihBi", result["packets"][0][1]),
            (7, 3, -18, 4, 3, -1),
        )
        self.assertEqual(
            struct.unpack(">BiiB", result["packets"][-2][1]), (0, 22534, 2536, 0)
        )
        self.assertEqual(
            result["packets"][-1], (12344, rii_zaap_scene.ELEMENT_STATE_PAYLOAD)
        )
        self.assertEqual(record.call_args.args[2], rii_zaap_scene.START_EVENT_KEY)
        self.assertEqual(persist.call_args.args[2]["objectives"], [10967])
        self.assertEqual(persist.call_args.args[2]["completed"], [5278])
        self.assertEqual(store.lock_character.call_args.kwargs["selected"], True)
        self.assertEqual(db.execute.call_count, 4)

    def test_begin_replay_is_silent_and_does_not_rewrite_progress(self):
        after = state()
        after["objectives"] = [10967]
        after["completed"] = [5278]
        payload = {
            "kind": "rii_zaap_scene",
            "character_id": 7,
            "element_id": 34719,
            "action_id": 5,
            "scenario_event": 22534,
            "objective_id": 10967,
            "quest_id": 5278,
        }
        store, _db = self._store_and_db(saved_state=after, starter={"payload": payload})
        with patch(
            "wakfu_server.achievements.storage.load_locked", return_value=after
        ), patch("wakfu_server.achievements.storage.record_event") as record, patch(
            "wakfu_server.achievements.storage.store"
        ) as persist:
            result = rii_zaap_scene.begin(store, 2, 3, self.character, self.activation)
        self.assertFalse(result["started"])
        self.assertEqual(result["packets"], ())
        record.assert_not_called()
        persist.assert_not_called()

    def test_callback_is_owner_pending_and_idempotent_without_teleport(self):
        callback_body = struct.pack(">i", 22534)
        starter = {"payload": rii_zaap_scene._start_payload(7)}
        mid_scene = dict(self.character, x=8, y=-20, z=5)
        route = {
            "direction": 3,
            "destination": {
                "map_id": 895,
                "instance_id": 0,
                "x": -8,
                "y": -1,
                "z": 18,
            },
        }
        arrival = dict(mid_scene, map_id=895, x=-8, y=-1, z=18)
        store, _db = self._store_and_db(current=mid_scene, starter=starter)
        store.transition_map_in_transaction.return_value = arrival
        store.character.side_effect = [mid_scene, arrival]
        with patch(
            "wakfu_server.achievements.storage.record_event", return_value=True
        ) as record, patch(
            "wakfu_server.mission_transport.transition",
            return_value=(arrival, [(13974, b"arrival"), (13832, b"mission")]),
        ) as transition, patch(
            "wakfu_server.rii_zaap_scene.departure_route", return_value=route
        ) as route_resolver, patch(
            "wakfu_server.astrub_arrival_scene.enter",
            return_value=[(13974, b"arrival"), (13832, b"mission")],
        ) as enter_arrival:
            saved, packets, used_route = rii_zaap_scene.finish(
                store,
                2,
                3,
                mid_scene,
                callback_body,
                pending_character_id=7,
            )
        self.assertEqual(saved, arrival)
        self.assertEqual(_db.execute.call_count, 3)
        self.assertEqual(packets, ((13974, b"arrival"), (13832, b"mission")))
        self.assertEqual(used_route, route)
        route_resolver.assert_called_once_with()
        record.assert_called_once()
        transition.assert_not_called()
        enter_arrival.assert_called_once_with(
            _db, store, mid_scene, dict(mid_scene, map_id=895, x=-8, y=-1, z=18)
        )
        store.transition_map_in_transaction.assert_called_once_with(
            _db, 2, 3, 7, mid_scene, route["destination"]
        )

        with self.assertRaisesRegex(ValueError, "not pending"):
            rii_zaap_scene.finish(
                store,
                2,
                3,
                mid_scene,
                callback_body,
                route=route,
                pending_character_id=8,
            )
        with self.assertRaisesRegex(ValueError, "not pending"):
            rii_zaap_scene.finish(
                store,
                2,
                3,
                mid_scene,
                callback_body,
                route=route,
                pending_character_id=7,
                in_combat=True,
            )

        callback_receipt = {
            "payload": {
                "kind": "rii_zaap_scene_callback",
                "character_id": 7,
                "scenario_event": 22534,
            }
        }
        replay_store, _db = self._store_and_db(
            current=mid_scene, starter=starter, callback=callback_receipt
        )
        replay_store.transition_map_in_transaction.return_value = arrival
        replay_store.character.side_effect = [mid_scene, arrival]
        with patch("wakfu_server.achievements.storage.record_event") as record, patch(
            "wakfu_server.rii_zaap_scene.departure_route", return_value=route
        ), patch(
            "wakfu_server.astrub_arrival_scene.enter", return_value=[]
        ) as enter_arrival:
            saved, packets, _route = rii_zaap_scene.finish(
                replay_store,
                2,
                3,
                mid_scene,
                callback_body,
                route=route,
                pending_character_id=7,
            )
        self.assertEqual(saved, arrival)
        self.assertEqual(packets, ())
        record.assert_not_called()
        enter_arrival.assert_called_once()

        with patch(
            "wakfu_server.rii_zaap_scene.departure_route", return_value=route
        ), patch("wakfu_server.achievements.storage.record_event") as record:
            with self.assertRaisesRegex(ValueError, "differs from installed"):
                rii_zaap_scene.finish(
                    replay_store,
                    2,
                    3,
                    mid_scene,
                    callback_body,
                    route={**route, "destination_id": 123},
                    pending_character_id=7,
                )
        record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
