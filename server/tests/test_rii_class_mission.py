import struct
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_class_mission


def state():
    return {
        "variables": {},
        "tracking": [],
        "recent": [],
        "completion_dates": {},
        "running": [],
        "completed": [],
        "objectives": [],
    }


class RiiClassReminderTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.db.execute.return_value.fetchone.return_value = {
            "data": {
                "native": {
                    "d": 5144,
                    "native_class": "aJM",
                    "aqb": True,
                    "isVisible": True,
                    "aHe": "GetRealLevel() < 30",
                    "bwX": 5160,
                    "cjI": "",
                    "cjU": 0,
                    "getDuration": 0,
                    "cjK": [],
                    "cjJ": [{"d": 10577, "ckc": "", "cke": "", "ckf": []}],
                }
            }
        }
        self.store = SimpleNamespace(
            now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        self.character = {
            "id": 7,
            "account_id": 2,
            "map_id": 1385,
            "instance_id": 0,
            "level": 1,
        }
        self.current = state()
        for patcher in (
            patch.object(
                rii_class_mission.storage,
                "load_locked",
                side_effect=lambda *a: self.current,
            ),
            patch.object(rii_class_mission.storage, "store", side_effect=self.save),
            patch.object(rii_class_mission.storage, "record_event", return_value=True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def save(self, db, identity, value):
        self.current = value

    def test_arrival_tracks_and_level_crossing_completes_once(self):
        packets = rii_class_mission.start(
            self.db, self.store, self.character, previous_map=527
        )
        self.assertEqual([p[0] for p in packets], [13312, 13371])
        self.assertEqual(self.current["running"], [5144])
        self.assertEqual(self.current["tracking"], [5144])
        self.assertEqual(
            rii_class_mission.reached_level(self.db, self.store, self.character, 29), []
        )
        packets = rii_class_mission.reached_level(
            self.db, self.store, self.character, 30
        )
        self.assertEqual([p[0] for p in packets], [13371, 13832, 13422])
        self.assertEqual(struct.unpack(">qi", packets[1][1]), (7, 10577))
        self.assertEqual(self.current["completed"], [5144])
        self.assertEqual(self.current["objectives"], [10577])
        self.assertEqual(self.current["tracking"], [])
        self.assertEqual(
            rii_class_mission.reached_level(self.db, self.store, self.character, 30), []
        )

    def test_no_start_for_above_limit_or_within_island(self):
        self.assertEqual(
            rii_class_mission.start(
                self.db, self.store, {**self.character, "level": 30}, previous_map=527
            ),
            [],
        )
        self.assertEqual(
            rii_class_mission.start(
                self.db, self.store, self.character, previous_map=1385
            ),
            [],
        )
        self.assertEqual(self.current, state())
        self.db.execute.assert_not_called()

    def test_mismatched_native_contract_does_not_start(self):
        self.db.execute.return_value.fetchone.return_value["data"]["native"][
            "aqb"
        ] = False
        with self.assertRaises(ValueError):
            rii_class_mission.start(
                self.db, self.store, self.character, previous_map=527
            )
        self.assertEqual(self.current, state())

    def test_journal_reconnect_preserves_arrival_date(self):
        from wakfu_server.achievements import service

        class Db:
            def execute(self, query, args):
                self.query, self.args = query, args
                return self

            def fetchall(self):
                return []

            def fetchone(self):
                if (
                    "character_achievement_events" in self.query
                    and self.args[1] == "rii-class-reminder:start"
                ):
                    return {"payload": {"accepted_at_ms": 1767225600000}}
                return None

        for key in ("running", "completed"):
            progress = state()
            progress[key] = [5144]
            body = service._journal_section(Db(), progress, {}, 7)[2:-1]
            self.assertEqual(
                struct.unpack_from(">iBBBB", body, 13),
                (5144, key == "running", key == "completed", 0, 1),
            )
            self.assertEqual(struct.unpack_from(">q", body, 21)[0], 1767225600000)


if __name__ == "__main__":
    unittest.main()
