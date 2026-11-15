"""Rii departure starts only with a newly settled guardian attempt."""

import struct
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_departure, wire, service


def state():
    return {
        "running": [5146],
        "completed": [],
        "objectives": [10582, 10583],
        "tracking": [5146],
        "recent": [],
        "completion_dates": {},
        "variables": {},
    }


class RiiDepartureTests(unittest.TestCase):
    def setUp(self):
        self.before = state()
        self.after = deepcopy(self.before)
        self.after.update(
            running=[], completed=[5146], objectives=[10582, 10583, 10584], tracking=[]
        )
        self.plan = (self.after, [], [10584], [5146])
        self.character = {"id": 12}
        self.db = Mock()
        self.db.execute.return_value.fetchone.return_value = {
            "data": {
                "native": {
                    "d": 5161,
                    "native_class": "aJM",
                    "aqb": False,
                    "cjI": "",
                    "aHe": "IsAchievementActive(5146)",
                    "cjJ": [{"d": 10624}],
                }
            }
        }
        self.record = patch.object(
            rii_departure.storage, "record_event", return_value=True
        )
        self.record_mock = self.record.start()
        self.addCleanup(self.record.stop)

    def activate(self, plan=None, before=None):
        return rii_departure.activate(
            self.db,
            None,
            self.character,
            self.before if before is None else before,
            self.plan if plan is None else plan,
            now_ms=1234,
        )

    def test_guardian_completion_starts_tracks_and_announces(self):
        result = self.activate()
        self.assertEqual(result[0]["running"], [5161])
        self.assertEqual(result[0]["tracking"], [5161])
        self.assertEqual(self.after["running"], [])
        self.assertEqual(
            self.record_mock.call_args.args[2], "rii-departure-activation:5161"
        )
        packets = wire.changes(12, self.before, result[0], result[2], result[3], 1234)
        # Official order at 19:42:39: the guardian objective marks and both
        # completions arrive before the newly activated departure quest.
        self.assertEqual(
            [packet[0] for packet in packets], [13832, 13422, 13371, 13312, 13371]
        )

    def test_other_completion_and_existing_departure_are_unchanged(self):
        other = (self.after, [], [], [])
        self.assertIs(self.activate(other), other)
        self.after["running"] = [5161]
        self.assertIs(self.activate(), self.plan)
        self.record_mock.assert_not_called()
        self.db.execute.assert_not_called()

    def test_rejects_forged_or_replayed_transition_and_bad_definition(self):
        with self.assertRaises(ValueError):
            self.activate((self.after, [], [], [5146]))
        invalid_before = deepcopy(self.before)
        invalid_before["completed"].append(5146)
        with self.assertRaises(ValueError):
            self.activate(before=invalid_before)
        self.db.execute.return_value.fetchone.return_value["data"]["native"]["cjJ"] = []
        with self.assertRaises(ValueError):
            self.activate()
        self.record_mock.assert_not_called()

    def test_receipt_conflict_does_not_return_a_mutated_plan(self):
        self.record_mock.return_value = False
        with self.assertRaises(ValueError):
            self.activate()
        self.assertEqual(self.after["running"], [])

    def test_journal_recovers_departure_acceptance_time(self):
        class Db:
            def execute(self, query, args):
                self.query, self.args = query, args
                return self

            def fetchall(self):
                return []

            def fetchone(self):
                if "character_achievement_events" in self.query:
                    if self.args[1] == "rii-departure-activation:5161":
                        return {"payload": {"accepted_at_ms": 1234}}
                return None

        current = state()
        current.update(running=[5161], tracking=[5161])
        raw = service._journal_section(Db(), current, {}, 12)
        self.assertEqual(struct.unpack_from(">iBBBB", raw, 15), (5161, 1, 0, 0, 1))
        self.assertEqual(struct.unpack_from(">q", raw, 23)[0], 1234)


if __name__ == "__main__":
    unittest.main()
