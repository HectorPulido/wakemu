"""Cron policy refresh must never fall back to a stale operational file."""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

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

    def test_each_tick_refreshes_and_invalid_policy_skips_stale_tasks(self):
        path = Path(__file__).resolve().parents[1] / "cron-service/service.py"
        spec = importlib.util.spec_from_file_location("cron_service_policy_test", path)
        service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(service)
        first = self.policy()
        disabled = self.policy()
        disabled["tasks"]["positions_flush"]["enabled"] = False
        scheduler = Mock()
        scheduler.tick.return_value = []
        seen = []
        scheduler.tick.side_effect = (
            lambda: seen.append(scheduler.tasks["positions_flush"]["enabled"]) or []
        )
        with patch.object(service, "provision"), patch.dict(
            service.os.environ, {"WAKFU_CRON_API_TOKEN_FILE": "/private/test-token"}
        ), patch.object(service, "Scheduler", return_value=scheduler), patch.object(
            service,
            "load_policy",
            side_effect=[first, ValueError("missing policy"), disabled],
        ), patch.object(
            service.time, "sleep", side_effect=[None, None, KeyboardInterrupt]
        ), patch(
            "builtins.print"
        ):
            with self.assertRaises(KeyboardInterrupt):
                service.run_scheduler(Mock(), Mock())
        self.assertEqual(seen, [True, False])
        self.assertEqual(scheduler.tick.call_count, 2)


if __name__ == "__main__":
    unittest.main()
