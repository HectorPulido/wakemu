"""Rii departure only advances for the owned, authorized Zaap journey."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.achievements import mission_toolkit, transport_missions
from wakfu_server import native_transports


class RiiTransportMissionTests(unittest.TestCase):
    def setUp(self):
        self.source = dict(
            id=42, account_id=3, map_id=1385, instance_id=0, x=3, y=-22, z=7
        )
        self.destination = dict(
            id=42, account_id=3, map_id=527, instance_id=0, x=0, y=32, z=0
        )
        self.route = dict(
            source_id=100,
            destination_id=101,
            destination={
                k: self.destination[k] for k in ("map_id", "instance_id", "x", "y", "z")
            },
        )
        self.db = Mock()
        self.db.execute.return_value.fetchone.return_value = {
            "data": {
                "native": {
                    "d": 5161,
                    "native_class": "aJM",
                    "aqb": False,
                    "cjI": "",
                    "cjK": [],
                    "cjJ": [{"d": 10624, "ckc": "", "cke": "", "ckf": []}],
                }
            }
        }
        self.store = SimpleNamespace(
            now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        self.state = {
            "variables": {},
            "tracking": [5161],
            "recent": [],
            "completion_dates": {},
            "running": [5161],
            "completed": [],
            "objectives": [],
        }
        for target, value in (
            ("ZAAPS", {100: {}, 101: {}}),
            ("OBJECTS", {100: {"map_id": 1385}, 101: {"map_id": 527}}),
        ):
            p = patch.object(native_transports, target, value)
            p.start()
            self.addCleanup(p.stop)
        self.patches = [
            patch("wakfu_server.achievements.service._owner"),
            patch("wakfu_server.achievements.service.drain_rewards", return_value=[]),
            patch.object(
                transport_missions.storage, "load_locked", return_value=self.state
            ),
            patch.object(transport_missions.storage, "record_event", return_value=True),
            patch.object(transport_missions.storage, "store"),
            patch.object(mission_toolkit, "settle_completions", return_value=[]),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def run_event(self, **overrides):
        return transport_missions.on_native_transport(
            self.db,
            self.store,
            overrides.get("source", self.source),
            overrides.get("destination", self.destination),
            overrides.get("route", self.route),
        )

    def test_qualified_journey_completes_active_quest(self):
        packets = self.run_event()
        self.assertTrue(packets)
        state = transport_missions.storage.store.call_args.args[2]
        self.assertEqual(state["completed"], [5161])
        self.assertEqual(state["objectives"], [10624])
        self.assertEqual(state["running"], [])
        self.assertEqual(state["tracking"], [])
        transport_missions.storage.record_event.assert_called_once()
        mission_toolkit.settle_completions.assert_called_once_with(
            self.db, self.store, self.destination, [5161]
        )

    def test_completion_followup_is_published_after_source_progress_and_rewards(self):
        def followup(db, store, character, completed):
            saved = transport_missions.storage.store.call_args.args[2]
            self.assertEqual(saved["completed"], completed)
            self.assertIn("5161", saved["completion_dates"])
            return [(13832, b"dependent-objective")]

        mission_toolkit.settle_completions.side_effect = followup
        packets = self.run_event()
        self.assertEqual(packets[-1], (13832, b"dependent-objective"))
        self.assertNotEqual(packets[0], packets[-1])

    def test_other_map_non_zaap_and_inactive_do_not_advance(self):
        self.assertEqual(self.run_event(source={**self.source, "map_id": 527}), [])
        self.assertEqual(self.run_event(route={**self.route, "source_id": 999}), [])
        self.state["running"].clear()
        self.assertEqual(self.run_event(), [])
        transport_missions.storage.store.assert_not_called()
        mission_toolkit.settle_completions.assert_not_called()

    def test_wrong_character_or_destination_rejected(self):
        with self.assertRaises(ValueError):
            self.run_event(destination={**self.destination, "id": 43})
        self.assertEqual(self.run_event(destination={**self.destination, "x": 99}), [])
        transport_missions.storage.store.assert_not_called()


if __name__ == "__main__":
    unittest.main()
