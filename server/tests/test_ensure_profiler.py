"""Pure configuration checks for profiler repair; these tests never invoke Docker."""

import tempfile
import unittest
from pathlib import Path

from tools.ensure_profiler import (
    binding_errors,
    check_status,
    expected_metrics_source,
    needs_recovery,
    recovery_overlay,
    validate_recovery,
)


def _container(name, source, destination, *, readonly=False):
    return {
        "Name": name,
        "Mounts": [{"Source": source, "Destination": destination, "RW": not readonly}],
    }


class EnsureProfilerTests(unittest.TestCase):
    def setUp(self):
        self.world = {
            "Id": "world-id-1",
            "State": {"Running": True, "Health": {"Status": "healthy"}},
            "Mounts": [
                _container("world", "/srv/wakemu/nondefault-data", "/data")["Mounts"][0]
            ],
        }
        expected = "/srv/wakemu/nondefault-data/logs/profiles"
        self.profiler = {
            "Id": "profiler-id-1",
            "Image": "sha256:profiler-image",
            "State": {"Running": True, "Health": {"Status": "healthy"}},
            "HostConfig": {"PidMode": "container:world-id-1"},
            "Mounts": [
                _container("profiler", expected, "/metrics", readonly=True)["Mounts"][
                    0
                ],
                _container("profiler", "/srv/wakemu/archive", "/profiles")["Mounts"][0],
            ],
            "Config": {"Image": "profiler:old-tag"},
        }

    def test_live_world_data_mount_is_the_metrics_authority(self):
        with tempfile.TemporaryDirectory() as cwd:
            Path(cwd, "logs", "profiles").mkdir(parents=True)
            self.assertEqual(
                expected_metrics_source(self.world),
                "/srv/wakemu/nondefault-data/logs/profiles",
            )
            self.assertNotEqual(
                expected_metrics_source(self.world), str(Path(cwd, "logs", "profiles"))
            )
        self.assertEqual(binding_errors(self.world, self.profiler), [])
        self.assertFalse(needs_recovery(self.world, self.profiler))

    def test_healthy_profiler_with_wrong_metrics_mount_still_needs_recovery(self):
        wrong = "/tmp/staging/logs/profiles"
        self.profiler["Mounts"][0]["Source"] = wrong
        self.assertIn(
            "world_metrics_storage_mismatch", binding_errors(self.world, self.profiler)
        )
        self.assertTrue(needs_recovery(self.world, self.profiler))

    def test_recovery_pins_metrics_readonly_and_preserves_archive_and_image(self):
        overlay = recovery_overlay(Path("/stage/project"), self.world, self.profiler)
        service = overlay["services"]["profiler"]
        self.assertEqual(service["pid"], "container:world-id-1")
        self.assertEqual(service["image"], "sha256:profiler-image")
        metrics = next(row for row in service["volumes"] if row["target"] == "/metrics")
        archive = next(
            row for row in service["volumes"] if row["target"] == "/profiles"
        )
        self.assertEqual(metrics["source"], "/srv/wakemu/nondefault-data/logs/profiles")
        self.assertTrue(metrics["read_only"])
        self.assertEqual(archive["source"], "/srv/wakemu/archive")

    def test_binding_validation_requires_world_pid_and_readonly_metrics(self):
        self.profiler["HostConfig"]["PidMode"] = "container:old-world"
        self.profiler["Mounts"][0]["RW"] = True
        errors = binding_errors(self.world, self.profiler)
        self.assertIn("world_pid_namespace_mismatch", errors)
        self.assertIn("world_metrics_mount_not_read_only", errors)

    def test_recovery_rejects_world_replacement_during_repair(self):
        overlay = recovery_overlay(Path("/stage/project"), self.world, self.profiler)
        changed = dict(self.world, Id="replacement-world-id")
        with self.assertRaisesRegex(RuntimeError, "World changed concurrently"):
            validate_recovery(self.world, changed, self.profiler, overlay)

    def test_check_reports_stopped_world_without_claiming_recovery(self):
        stopped = dict(
            self.world, State={"Running": False, "Health": {"Status": "healthy"}}
        )
        status = check_status(stopped, self.profiler)
        self.assertIn("world_not_running", status["errors"])
        self.assertFalse(status["recoveryNeeded"])
        self.assertEqual(status["services"]["world"]["running"], False)

    def test_check_reports_stopped_or_unhealthy_profiler_as_recoverable(self):
        stopped = dict(
            self.profiler,
            State={"Running": False, "Health": {"Status": "healthy"}},
        )
        status = check_status(self.world, stopped)
        self.assertIn("profiler_not_running", status["errors"])
        self.assertTrue(status["recoveryNeeded"])

        unhealthy = dict(
            self.profiler,
            State={"Running": True, "Health": {"Status": "unhealthy"}},
        )
        status = check_status(self.world, unhealthy)
        self.assertIn("profiler_not_healthy", status["errors"])
        self.assertTrue(status["recoveryNeeded"])


if __name__ == "__main__":
    unittest.main()
