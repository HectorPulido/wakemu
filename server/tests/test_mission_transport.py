"""Map movement and mission events share the same transaction boundary."""
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from wakfu_server import mission_transport, rii_scenario
from wakfu_server.achievements import transport_missions, zone_missions


class MissionTransportTests(unittest.TestCase):
    def setUp(self):
        self.db = object()
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

        self.source = {"id": 7, "account_id": 1, "map_id": 527}
        self.saved = {"id": 7, "account_id": 1, "map_id": 1385}
        self.route = {"destination": {"map_id": 1385}}
        self.store = Mock()
        self.store.connection.side_effect = connection
        self.store.transition_map_in_transaction.return_value = self.saved

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
        self.assertEqual(self.lifecycle, ["begin", "commit"])

    def test_boat_does_not_emit_zaap_fact(self):
        with patch.object(
            zone_missions, "enter_rii", return_value=[]
        ) as entry, patch.object(
            transport_missions, "on_native_transport"
        ) as exit_event:
            _, packets = mission_transport.transition(
                self.store, 1, 3, self.source, self.route, native_zaap=False
            )
        self.assertEqual(packets, [rii_scenario.packet(rii_scenario.ENTRY)])
        entry.assert_called_once()
        exit_event.assert_not_called()
        self.assertEqual(self.lifecycle, ["begin", "commit"])

    def test_failed_mission_event_rolls_back_move(self):
        with patch.object(
            zone_missions, "enter_rii", side_effect=ValueError("bad definition")
        ):
            with self.assertRaisesRegex(ValueError, "bad definition"):
                mission_transport.transition(
                    self.store, 1, 3, self.source, self.route, native_zaap=True
                )
        self.assertEqual(self.lifecycle, ["begin", "rollback"])


if __name__ == "__main__":
    unittest.main()
