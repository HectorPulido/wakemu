"""Cron policy refresh must never fall back to a stale operational file."""
from contextlib import contextmanager
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from wakfu_server.storage.cron_policy import load_policy, validate_policy


class CronDatabasePolicyTests(unittest.TestCase):
    def policy(self):
        seed = (
            Path(__file__).resolve().parents[1]
            / "migrations/151_cron_scheduler_policy.sql"
        ).read_text()
        return json.loads(seed.split("$cron_policy$")[1])

    def test_seed_preserves_only_positions_enabled(self):
        policy = validate_policy(self.policy())
        self.assertEqual(len(policy["tasks"]), 5)
        self.assertEqual(
            [name for name, task in policy["tasks"].items() if task["enabled"]],
            ["positions_flush"],
        )
        self.assertEqual(policy["poll_seconds"], 1)

    def test_malformed_values_are_rejected(self):
        for value in (None, [], {}, {"tasks": []}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_policy(value)
        for field, value in (
            ("interval", 0),
            ("interval", True),
            ("lease_seconds", float("nan")),
            ("retry_seconds", -1),
            ("max_attempts", 1.5),
            ("enabled", "true"),
            ("url", "file:///tmp/task"),
            ("body", []),
        ):
            policy = self.policy()
            policy["tasks"]["positions_flush"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_policy(policy)

    def test_database_setting_is_required_and_read_without_mutation(self):
        database = Mock()
        connection = Mock()

        @contextmanager
        def connect():
            yield connection

        database.connection = connect
        connection.execute.return_value.fetchone.return_value = None
        with self.assertRaisesRegex(ValueError, "Missing database setting"):
            load_policy(database)
        value = self.policy()
        connection.execute.return_value.fetchone.return_value = {"value": value}
        actual = load_policy(database)
        actual["tasks"].clear()
        self.assertEqual(len(value["tasks"]), 5)
        connection.execute.assert_called_with(
            "SELECT value FROM settings WHERE name = %s", ("cron_scheduler_policy",)
        )

if __name__ == "__main__":
    unittest.main()
