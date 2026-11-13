"""The Rii entry policy starts its mission without manufacturing progress."""
import struct
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.achievements import zone_missions


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


class RiiEntryMissionTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.definitions = {
            identity: {
                "d": identity,
                "native_class": "aJM",
                "aqb": False,
                "cjI": "",
                "cjU": 0,
                "getDuration": 0,
            }
            for identity in (5160, 5146)
        }
        self.db.execute.side_effect = lambda sql, args: Mock(
            fetchone=Mock(return_value={"data": {"native": self.definitions[args[0]]}})
        )
        self.store = SimpleNamespace(
            now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        self.character = {"id": 7, "map_id": 1385, "instance_id": 0}
        self.current = state()
        self.patches = [
            patch.object(
                zone_missions.storage,
                "load_locked",
                side_effect=lambda *args: self.current,
            ),
            patch.object(zone_missions.storage, "record_event", return_value=True),
            patch.object(zone_missions.storage, "store", side_effect=self.save),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def save(self, db, character_id, value):
        self.current = value

    def test_qualified_arrival_starts_and_tracks_once_without_objectives_or_rewards(
        self,
    ):
        packets = zone_missions.enter_rii(
            self.db, self.store, self.character, previous_map=527
        )
        self.assertTrue(packets)
        self.assertEqual(self.current["running"], [5146, 5160])
        self.assertEqual(set(self.current["tracking"]), {5146, 5160})
        self.assertEqual(self.current["completed"], [])
        self.assertEqual(self.current["objectives"], [])
        receipt = zone_missions.storage.record_event.call_args.args[3]
        self.assertEqual(receipt["accepted_at_ms"], 1767225600000)
        self.assertEqual(
            zone_missions.enter_rii(
                self.db, self.store, self.character, previous_map=527
            ),
            [],
        )
        self.current["running"].clear()
        self.current["completed"].extend((5146, 5160))
        self.assertEqual(
            zone_missions.enter_rii(
                self.db, self.store, self.character, previous_map=527
            ),
            [],
        )

    def test_reconnect_other_map_and_instance_do_not_activate(self):
        for previous, current in (
            (1385, self.character),
            (527, {**self.character, "map_id": 527}),
            (527, {**self.character, "instance_id": 8}),
        ):
            self.assertEqual(
                zone_missions.enter_rii(
                    self.db, self.store, current, previous_map=previous
                ),
                [],
            )
        self.db.execute.assert_not_called()

    def test_character_created_directly_on_rii_starts_the_same_missions(self):
        packets = zone_missions.enter_rii(
            self.db, self.store, self.character, previous_map=None
        )
        self.assertTrue(packets)
        self.assertEqual(self.current["running"], [5146, 5160])
        self.assertEqual(set(self.current["tracking"]), {5146, 5160})

    def test_definition_mismatch_fails_closed(self):
        self.definitions[5146]["cjU"] = 1
        with self.assertRaises(ValueError):
            zone_missions.enter_rii(
                self.db, self.store, self.character, previous_map=527
            )
        self.assertEqual(self.current, state())

    def test_journal_reconnect_uses_receipt_for_active_and_completed(self):
        from wakfu_server.achievements import service

        class Db:
            def execute(self, query, args):
                self.query = query
                return self

            def fetchall(self):
                return []

            def fetchone(self):
                if "character_achievement_events" in self.query:
                    return {"payload": {"accepted_at_ms": 1767225600000}}
                return None

        for key in ("running", "completed"):
            progress = state()
            progress[key] = [5160]
            raw = service._journal_section(Db(), progress, {}, 7)
            body = raw[2:-1]
            self.assertEqual(
                struct.unpack_from(">iBBBB", body, 13),
                (5160, key == "running", key == "completed", 0, 1),
            )
            self.assertEqual(struct.unpack_from(">q", body, 21)[0], 1767225600000)


if __name__ == "__main__":
    unittest.main()
