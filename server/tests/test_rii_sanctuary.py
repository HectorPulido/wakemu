"""Rii sanctuary entry progresses its already active first objective."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_sanctuary


class SanctuaryEntryTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "variables": {},
            "tracking": [],
            "recent": [],
            "completion_dates": {},
            "running": [5146],
            "completed": [],
            "objectives": [],
        }
        self.definition = {
            "d": 5146,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjJ": [{"d": 10582}, {"d": 10583}, {"d": 10584}],
        }
        self.db = Mock()
        self.db.execute.return_value.fetchone.return_value = {
            "data": {"native": self.definition}
        }
        self.store = SimpleNamespace(
            now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        self.source = {"id": 7, "account_id": 9, "map_id": 1385, "instance_id": 0}
        self.destination = {**self.source, "map_id": 1387, "level": 6}
        self.route = {"interactive_element_id": 34619, "destination_id": 4560}
        self.patches = [
            patch.object(
                rii_sanctuary.storage, "load_locked", side_effect=lambda *a: self.state
            ),
            patch.object(rii_sanctuary.storage, "record_event", return_value=True),
            patch.object(rii_sanctuary.storage, "store", side_effect=self.save),
            patch.object(
                rii_sanctuary.mission_progress,
                "advance_objective",
                side_effect=self.advance,
            ),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def save(self, db, character_id, state):
        self.state = state

    def advance(self, state, definition, objective, **kwargs):
        state["objectives"].append(objective)
        return state, [], [objective], []

    def test_eligible_entry_progresses_once(self):
        packets = rii_sanctuary.enter(
            self.db, self.store, self.source, self.destination, self.route
        )
        self.assertTrue(packets)
        self.assertEqual(self.state["running"], [5146])
        self.assertEqual(self.state["tracking"], [])
        self.assertEqual(self.state["objectives"], [10582])
        self.assertEqual(
            rii_sanctuary.enter(
                self.db, self.store, self.source, self.destination, self.route
            ),
            [],
        )

    def test_entry_refreshes_the_tracked_quest_after_objective_completion(self):
        self.state["tracking"] = [5146]
        packets = rii_sanctuary.enter(
            self.db, self.store, self.source, self.destination, self.route
        )
        self.assertEqual([13832, 13371, 13371], [opcode for opcode, _ in packets])
        self.assertEqual(self.state["tracking"], [5146])
        self.assertEqual(self.state["objectives"], [10582])

    def test_low_level_wrong_route_and_completed_do_nothing(self):
        self.assertEqual(
            rii_sanctuary.enter(
                self.db,
                self.store,
                self.source,
                {**self.destination, "level": 5},
                self.route,
            ),
            [],
        )
        self.assertEqual(
            rii_sanctuary.enter(
                self.db,
                self.store,
                self.source,
                self.destination,
                {**self.route, "destination_id": 1},
            ),
            [],
        )
        self.state["completed"] = [5146]
        self.assertEqual(
            rii_sanctuary.enter(
                self.db, self.store, self.source, self.destination, self.route
            ),
            [],
        )
        self.db.execute.assert_not_called()

    def test_wrong_definition_or_identity_fails(self):
        self.definition["cjJ"] = []
        with self.assertRaises(ValueError):
            rii_sanctuary.enter(
                self.db, self.store, self.source, self.destination, self.route
            )
        with self.assertRaises(ValueError):
            rii_sanctuary.enter(
                self.db,
                self.store,
                self.source,
                {**self.destination, "id": 8},
                self.route,
            )


if __name__ == "__main__":
    unittest.main()
