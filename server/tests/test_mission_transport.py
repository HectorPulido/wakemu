"""Map movement and mission events share the same transaction boundary."""
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from wakfu_server import mission_transport, rii_scenario
from wakfu_server.achievements import transport_missions, zone_missions


class MissionTransportTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.db.execute.return_value.fetchone.return_value = {"id": 1}
        self.lifecycle = []

        @contextmanager
        def connection():
            self.lifecycle.append("begin")
            try:
                yield self.db
            except Exception:
                self.lifecycle.append("rollback")
                raise
            else:
                self.lifecycle.append("commit")

        self.source = {"id": 7, "account_id": 1, "map_id": 527, "instance_id": 0}
        self.saved = {
            "id": 7,
            "account_id": 1,
            "map_id": 1385,
            "instance_id": 0,
            "level": 20,
        }
        self.route = {"destination": {"map_id": 1385}}
        self.store = Mock()
        self.store.connection.side_effect = connection
        self.store.transition_map_in_transaction.side_effect = self.move
        self.store.character.return_value = self.saved
        class_mission = patch(
            "wakfu_server.achievements.rii_class_mission.start", return_value=[]
        )
        class_mission.start()
        self.addCleanup(class_mission.stop)
        map_enter = patch(
            "wakfu_server.achievements.mission_toolkit.settle",
            side_effect=self.settle_mission_event,
        )
        self.map_enter = map_enter.start()
        self.addCleanup(map_enter.stop)

    def settle_mission_event(self, _db, _store, _character, *, token, kind, reference):
        self.lifecycle.append(kind)
        if kind == "map_enter":
            return [(3, b"map-enter")]
        if kind == "map_departure":
            return []
        raise AssertionError((kind, reference))

    def move(self, *_args):
        self.lifecycle.append("compare-and-set")
        return self.saved

    def test_zaap_move_and_mission_events_commit_together(self):
        with patch.object(
            zone_missions, "enter_rii", return_value=[(1, b"a")]
        ) as entry, patch.object(
            transport_missions, "on_native_transport", return_value=[(2, b"b")]
        ) as exit_event:
            saved, packets = mission_transport.transition(
                self.store, 1, 3, self.source, self.route, native_zaap=True
            )
        self.assertEqual(
            (saved, packets),
            (
                self.saved,
                [
                    (1, b"a"),
                    (2, b"b"),
                    (3, b"map-enter"),
                    rii_scenario.packet(rii_scenario.ENTRY),
                    rii_scenario.packet(rii_scenario.INTRO),
                ],
            ),
        )
        self.store.transition_map_in_transaction.assert_called_once_with(
            self.db, 1, 3, 7, self.source, self.route["destination"]
        )
        entry.assert_called_once_with(self.db, self.store, self.saved, previous_map=527)
        exit_event.assert_called_once_with(
            self.db, self.store, self.source, self.saved, self.route
        )
        self.assertEqual(self.map_enter.call_count, 2)
        self.assertEqual(
            [call.kwargs["kind"] for call in self.map_enter.call_args_list],
            ["map_departure", "map_enter"],
        )
        self.assertEqual(self.map_enter.call_args_list[0].kwargs["reference"], 1385)
        self.assertEqual(self.map_enter.call_args_list[1].kwargs["reference"], 1385)
        self.assertEqual(
            self.lifecycle,
            ["begin", "map_departure", "compare-and-set", "map_enter", "commit"],
        )

    def test_boat_does_not_emit_zaap_fact(self):
        with patch.object(
            zone_missions, "enter_rii", return_value=[]
        ) as entry, patch.object(
            transport_missions, "on_native_transport"
        ) as exit_event:
            _, packets = mission_transport.transition(
                self.store, 1, 3, self.source, self.route, native_zaap=False
            )
        self.assertEqual(
            packets,
            [(3, b"map-enter"), rii_scenario.packet(rii_scenario.ENTRY)],
        )
        entry.assert_called_once()
        exit_event.assert_not_called()
        self.assertEqual(self.map_enter.call_count, 2)
        self.assertEqual(
            [call.kwargs["kind"] for call in self.map_enter.call_args_list],
            ["map_departure", "map_enter"],
        )
        self.assertEqual(
            self.lifecycle,
            ["begin", "map_departure", "compare-and-set", "map_enter", "commit"],
        )

    def test_failed_mission_event_rolls_back_move(self):
        with patch.object(
            zone_missions, "enter_rii", side_effect=ValueError("bad definition")
        ):
            with self.assertRaisesRegex(ValueError, "bad definition"):
                mission_transport.transition(
                    self.store, 1, 3, self.source, self.route, native_zaap=True
                )
        self.assertEqual(
            self.lifecycle,
            ["begin", "map_departure", "compare-and-set", "rollback"],
        )


if __name__ == "__main__":
    unittest.main()
