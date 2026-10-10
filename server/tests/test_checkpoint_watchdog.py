import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest

from wakfu_server.checkpoint_watchdog import CheckpointWatchdog


class RecordingBackend:
    def __init__(self, *, arm_error=None, cancel_error=None):
        self.arm_error = arm_error
        self.cancel_error = cancel_error
        self.armed = []
        self.cancelled = 0

    def dump_traceback_later(self, timeout, *, repeat, file, exit):
        self.armed.append((timeout, repeat, file, exit))
        if self.arm_error is not None:
            raise self.arm_error

    def cancel_dump_traceback_later(self):
        self.cancelled += 1
        if self.cancel_error is not None:
            raise self.cancel_error


class CheckpointWatchdogTests(unittest.TestCase):
    def make_watchdog(self, directory, backend, *, timeout=1.0):
        return CheckpointWatchdog(
            Path(directory) / "stacks.log", timeout=timeout, backend=backend
        )

    def test_overlapping_workers_arm_once_and_cancel_after_last_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = RecordingBackend()
            watchdog = self.make_watchdog(directory, backend)
            self.addCleanup(watchdog.close)
            first_entered = threading.Event()
            second_entered = threading.Event()
            release_first = threading.Event()
            release_second = threading.Event()
            errors = []

            def worker(entered, release):
                try:
                    with watchdog.watch():
                        entered.set()
                        if not release.wait(2):
                            raise TimeoutError("worker was not released")
                except Exception as error:
                    errors.append(error)

            first = threading.Thread(target=worker, args=(first_entered, release_first))
            second = threading.Thread(
                target=worker, args=(second_entered, release_second)
            )
            first.start()
            self.assertTrue(first_entered.wait(1))
            second.start()
            self.assertTrue(second_entered.wait(1))

            self.assertEqual(len(backend.armed), 1)
            self.assertEqual(watchdog.active, 2)
            release_first.set()
            first.join(1)
            self.assertFalse(first.is_alive())
            self.assertEqual(backend.cancelled, 0)
            self.assertEqual(watchdog.active, 1)

            release_second.set()
            second.join(1)
            self.assertFalse(second.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(watchdog.active, 0)
            self.assertEqual(backend.cancelled, 1)

    def test_body_exception_cleans_up_watch_and_preserves_original_error(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = RecordingBackend(
                cancel_error=RuntimeError("diagnostic cancel failed")
            )
            watchdog = self.make_watchdog(directory, backend)
            with self.assertRaisesRegex(LookupError, "flush failed"):
                with watchdog.watch():
                    raise LookupError("flush failed")
            self.assertEqual(watchdog.active, 0)
            self.assertFalse(watchdog.armed)
            self.assertEqual(backend.cancelled, 1)
            watchdog.close()
            self.assertTrue(watchdog.stream.closed)

    def test_backend_arm_failure_does_not_change_checkpoint_result(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = RecordingBackend(arm_error=OSError("diagnostic file unavailable"))
            watchdog = self.make_watchdog(directory, backend)
            self.addCleanup(watchdog.close)

            def checkpoint():
                with watchdog.watch():
                    return 7

            self.assertEqual(checkpoint(), 7)
            self.assertEqual(watchdog.active, 0)
            self.assertFalse(watchdog.armed)
            self.assertEqual(backend.cancelled, 0)

    def test_backend_cancel_failure_does_not_override_completed_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = RecordingBackend(
                cancel_error=RuntimeError("diagnostic cancel failed")
            )
            watchdog = self.make_watchdog(directory, backend)
            # If cleanup itself regresses, close the file without retrying the
            # failing backend cancellation from CheckpointWatchdog.close().
            self.addCleanup(watchdog.stream.close)

            def checkpoint():
                with watchdog.watch():
                    return 11

            self.assertEqual(checkpoint(), 11)
            self.assertEqual(watchdog.active, 0)

    def test_native_faulthandler_dumps_blocked_worker_without_terminating_process(self):
        with tempfile.TemporaryDirectory() as directory:
            stack_path = Path(directory) / "native-stacks.log"
            script = textwrap.dedent(
                """
                from pathlib import Path
                import threading
                import time
                import sys
                from wakfu_server.checkpoint_watchdog import CheckpointWatchdog

                watchdog = CheckpointWatchdog(Path(sys.argv[1]), timeout=0.05)
                entered = threading.Event()
                release = threading.Event()

                def slow_checkpoint():
                    with watchdog.watch():
                        entered.set()
                        release.wait(2)

                worker = threading.Thread(target=slow_checkpoint, name="slow-checkpoint-worker")
                worker.start()
                if not entered.wait(1):
                    raise TimeoutError("worker did not enter checkpoint")
                time.sleep(0.2)
                release.set()
                worker.join(1)
                if worker.is_alive():
                    raise TimeoutError("worker did not leave checkpoint")
                watchdog.close()
                print("checkpoint-completed")
                """
            )
            environment = dict(os.environ)
            source_root = str(Path(__file__).parents[1])
            environment["PYTHONPATH"] = (
                source_root + os.pathsep + environment.get("PYTHONPATH", "")
            )
            completed = subprocess.run(
                [sys.executable, "-c", script, str(stack_path)],
                capture_output=True,
                text=True,
                timeout=5,
                env=environment,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("checkpoint-completed", completed.stdout)
            stack = stack_path.read_text()
            self.assertIn("Timeout", stack)
            self.assertIn("slow_checkpoint", stack)


if __name__ == "__main__":
    unittest.main()
