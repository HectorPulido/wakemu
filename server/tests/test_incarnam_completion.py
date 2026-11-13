import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from wakfu_server.incarnam_completion import complete_after_rii_intro


class IncarnamCompletionTest(unittest.TestCase):
    def setUp(self):
        self.store = MagicMock()
        self.db = MagicMock()
        self.store.connection.return_value.__enter__.return_value = self.db
        self.store.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.character = {"id": 7, "map_id": 1385, "instance_id": 0}
        self.store.character.return_value = self.character
        self.db.execute.return_value.fetchone.return_value = {
            "data": {"native": {"d": 5139}}
        }

    @patch("wakfu_server.incarnam_completion.mission_dependencies.settle")
    @patch("wakfu_server.incarnam_completion.mission_progress.advance_objective")
    @patch("wakfu_server.incarnam_completion.storage")
    def test_finishes_only_running_mission_once(self, storage, advance, settle):
        storage.load_locked.return_value = {"running": [5139], "objectives": []}
        storage.record_event.return_value = True
        advance.return_value = ("planned",)
        settle.return_value = {"packets": [(13832, b"ok")]}
        self.assertEqual(
            complete_after_rii_intro(self.store, 1, 2, self.character), [(13832, b"ok")]
        )
        self.assertEqual(advance.call_args.args[2], 10568)
        storage.load_locked.return_value = {"running": [], "objectives": [10568]}
        self.assertEqual(complete_after_rii_intro(self.store, 1, 2, self.character), [])
        self.assertEqual(settle.call_count, 1)

    @patch("wakfu_server.incarnam_completion.storage")
    def test_rejects_wrong_world(self, storage):
        self.store.character.return_value = dict(self.character, map_id=527)
        with self.assertRaises(ValueError):
            complete_after_rii_intro(self.store, 1, 2, self.character)
        storage.load_locked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
