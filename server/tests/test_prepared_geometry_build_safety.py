"""Offline geometry generation must bound concurrency and worker memory."""
import fcntl
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


_spec = importlib.util.spec_from_file_location(
    "geometry_builder",
    Path(__file__).parents[1] / "tools/prepare_geometry_artifacts.py",
)
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)


class GeometryBuildSafetyTests(unittest.TestCase):
    def test_small_worker_completes(self):
        builder.run_isolated([sys.executable, "-c", "pass"], 64)

    def test_failed_worker_is_not_reported_successful(self):
        with self.assertRaisesRegex(RuntimeError, "worker failed"):
            builder.run_isolated([sys.executable, "-c", "raise SystemExit(3)"], 64)

    def test_memory_watchdog_terminates_worker(self):
        started = []
        original = subprocess.Popen

        def capture(*args, **kwargs):
            worker = original(*args, **kwargs)
            started.append(worker)
            return worker

        with patch.object(
            builder.subprocess, "Popen", side_effect=capture
        ), patch.object(
            builder, "resident_kib", return_value=65 * 1024
        ), self.assertRaisesRegex(
            RuntimeError, "exceeded 64 MiB"
        ):
            builder.run_isolated(
                [sys.executable, "-c", "import time; time.sleep(30)"], 64
            )
        self.assertIsNotNone(started[0].poll())

    def test_second_coordinator_cannot_start_or_read_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            with (Path(directory) / ".build.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(
                    sys, "argv", ["builder", "--map", "527", "--output", directory]
                ), patch.object(
                    builder.native_catalog, "release"
                ) as release, self.assertRaisesRegex(
                    RuntimeError, "already running"
                ):
                    builder.main()
                release.assert_not_called()

    def test_coordinator_runs_one_worker_per_map_in_order(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            sys, "argv", ["builder", "--all", "--output", directory]
        ), patch.object(
            builder.native_catalog, "release", return_value="revision"
        ), patch.object(
            builder.native_catalog,
            "document_hashes",
            return_value={
                "combat-maps/527.json": "a",
                "combat-maps/9.json": "b",
                "combat-maps/index.json": "c",
            },
        ), patch.object(
            builder, "run_isolated"
        ) as run:
            builder.main()
            self.assertEqual(run.call_count, 2)
            self.assertEqual(
                [call.args[0][-3] for call in run.call_args_list], ["9", "527"]
            )
            self.assertTrue(all(call.args[1] == 512 for call in run.call_args_list))
