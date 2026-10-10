import threading
import unittest

from wakfu_server.storage.manual_checkpoint import ManualCheckpoint


class ManualCheckpointTests(unittest.TestCase):
    def test_request_returns_while_flush_runs_and_coalesces_listeners(self):
        entered = threading.Event()
        release = threading.Event()
        notifications = []
        notification_ready = threading.Event()
        calls = []

        def flush():
            calls.append(True)
            entered.set()
            self.assertTrue(release.wait(2))
            return 7

        checkpoint = ManualCheckpoint(flush)
        first = checkpoint.request(
            requester="alice",
            notify=lambda result: notifications.append(("old", result)),
        )
        self.assertEqual(first["status"], "running")
        self.assertTrue(entered.wait(1))

        second = checkpoint.request(
            requester="alice",
            notify=lambda result: (
                notifications.append(("new", result)),
                notification_ready.set(),
            ),
        )
        self.assertTrue(second["coalesced"])
        self.assertEqual(second["handle"], first["handle"])
        self.assertEqual(checkpoint.status(first["handle"])["status"], "running")
        self.assertEqual(len(calls), 1)

        release.set()
        self.assertTrue(notification_ready.wait(1))
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0][0], "new")
        self.assertEqual(notifications[0][1]["status"], "completed")
        self.assertEqual(checkpoint.status(first["handle"])["characters"], 7)

    def test_failure_is_sanitized_and_next_request_retries(self):
        calls = []

        def flush():
            calls.append(True)
            if len(calls) == 1:
                raise RuntimeError("secret-db-host and password=hidden")
            return 3

        checkpoint = ManualCheckpoint(flush)
        failed = checkpoint.request()
        self._wait_for_status(checkpoint, failed["handle"], "failed")
        failed_result = checkpoint.status(failed["handle"])
        self.assertEqual(failed_result["error_type"], "RuntimeError")
        self.assertNotIn("secret-db-host", str(failed_result))
        self.assertNotIn("hidden", str(failed_result))

        retried = checkpoint.request()
        self.assertNotEqual(retried["handle"], failed["handle"])
        self._wait_for_status(checkpoint, retried["handle"], "completed")
        self.assertEqual(checkpoint.status(retried["handle"])["characters"], 3)
        self.assertEqual(len(calls), 2)

    def test_result_history_is_bounded_and_old_handles_expire(self):
        checkpoint = ManualCheckpoint(lambda: 1, history_limit=2)
        handles = []
        for _ in range(3):
            result = checkpoint.request()
            handles.append(result["handle"])
            self._wait_for_status(checkpoint, result["handle"], "completed")

        self.assertEqual(len(checkpoint.results), 2)
        with self.assertRaisesRegex(ValueError, "desconocido o expirado"):
            checkpoint.status(handles[0])
        self.assertEqual(checkpoint.status(handles[1])["status"], "completed")
        self.assertEqual(checkpoint.status(handles[2])["status"], "completed")

    def _wait_for_status(self, checkpoint, handle, expected):
        deadline = threading.Event()
        for _ in range(200):
            result = checkpoint.status(handle)
            if result["status"] == expected:
                return
            deadline.wait(0.005)
        self.fail(f"checkpoint {handle} did not reach {expected}")


if __name__ == "__main__":
    unittest.main()
