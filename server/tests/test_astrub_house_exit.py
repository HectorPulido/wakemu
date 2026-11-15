"""Owned arrival-house trigger, progression and atomic scene transition."""

from copy import deepcopy
from datetime import datetime, timezone
import struct
import unittest
from unittest.mock import MagicMock, patch

from wakfu_server import astrub_house_exit as house


class AstrubHouseExitTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(
            id=7, account_id=2, map_id=895, instance_id=0, x=0, y=1, z=0
        )
        self.body = struct.pack(">qHH", 35386, 5, 0)

    def test_trigger_scope_and_native_approved_crossing(self):
        self.assertTrue(house.handles_activation(self.character, self.body))
        for changed in (
            dict(self.character, map_id=527),
            dict(self.character, instance_id=7),
        ):
            self.assertFalse(house.handles_activation(changed, self.body))
        self.assertFalse(house.handles_activation(self.character, b"short"))
        for position in ((0, 1, 0), (-1, 1, 0)):
            house._authorized_position(
                dict(self.character, **dict(zip(("x", "y", "z"), position)))
            )
        endpoint = dict(self.character, x=0, y=3)
        house._authorized_position(endpoint, ((0, 0, 0), (0, 1, 0), (0, 3, 0)))
        for approved in (
            (),
            ((0, 0, 0), (0, 3, 0)),
            ((0, 1, 0),),
            ((0, 1, True), (0, 3, 0)),
        ):
            with self.subTest(approved=approved), self.assertRaises(ValueError):
                house._authorized_position(endpoint, approved)

    def test_exit_objective_and_travel_share_owned_transaction(self):
        store = MagicMock()
        db = store.connection.return_value.__enter__.return_value
        store.character.return_value = dict(self.character)
        store.now.return_value = datetime(2026, 11, 14, tzinfo=timezone.utc)
        db.execute.return_value.fetchone.return_value = {
            "data": {"native": {"d": 5568}}
        }
        before = dict(running=[5568], objectives=[11508])
        after = dict(running=[5568], objectives=[11508, 11509])
        route = dict(
            source_map=895, destination=deepcopy(house.DESTINATION), direction=3
        )
        saved = dict(self.character, **house.DESTINATION)
        steps = []
        store.transition_map_in_transaction.side_effect = (
            lambda *args: steps.append(("move", args)) or saved
        )
        planned = (after, [], [11509], [])
        with patch.object(house, "_route", return_value=route), patch(
            "wakfu_server.achievements.storage.load_locked", return_value=before
        ), patch(
            "wakfu_server.achievements.storage.record_event",
            side_effect=lambda *a: steps.append(("receipt", a)) or True,
        ), patch(
            "wakfu_server.achievements.mission_progress.advance_objective",
            return_value=planned,
        ) as advance, patch(
            "wakfu_server.achievements.mission_dependencies.settle",
            side_effect=lambda *a, **k: steps.append(("settle", a))
            or {"packets": [(13832, b"objective")]},
        ) as settle:
            result = house.begin(store, 2, "lease", self.character, self.body)
        self.assertEqual([kind for kind, _ in steps], ["receipt", "settle", "move"])
        self.assertIs(steps[1][1][0], db)
        self.assertIs(steps[2][1][0], db)
        self.assertEqual(advance.call_args.args[2], 11509)
        self.assertEqual(
            result, dict(character=saved, packets=((13832, b"objective"),), route=route)
        )
        store.lock_character.assert_called_once_with(db, 2, "lease", 7, selected=True)

    def test_wrong_action_and_missing_talk_never_move_or_complete(self):
        store = MagicMock()
        store.character.return_value = dict(self.character)
        for body in (
            self.body[:-1],
            struct.pack(">qHH", 35386, 4, 0),
            struct.pack(">qHH", 35386, 5, 1),
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                house.begin(store, 2, "lease", self.character, body)
        with patch.object(house, "_route", return_value={}), patch(
            "wakfu_server.achievements.storage.load_locked",
            return_value=dict(running=[5568], objectives=[]),
        ), patch(
            "wakfu_server.achievements.storage.record_event"
        ) as record, self.assertRaisesRegex(
            ValueError, "introduction"
        ):
            house.begin(store, 2, "lease", self.character, self.body)
        record.assert_not_called()
        store.transition_map_in_transaction.assert_not_called()


if __name__ == "__main__":
    unittest.main()
