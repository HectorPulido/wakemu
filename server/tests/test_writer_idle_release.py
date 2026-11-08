"""Small actual-worker lifetime checks; no database, catalogs or large payloads."""
import sys
import unittest
import weakref
from pathlib import Path
from unittest.mock import patch

from wakfu_server.async_diagnostic_log import AsyncDiagnosticLog
from wakfu_server import combat_incident_capture as incidents


class WriterIdleReleaseTests(unittest.TestCase):
    def test_success_and_error_release_before_idle_and_preserve_error_counters(self):
        class Row(dict):
            pass

        for fail in (False, True):
            with self.subTest(worker="diagnostic", fail=fail):
                calls = []

                def write(rows):
                    calls.append(len(rows))
                    if fail:
                        raise OSError("bounded test write failure")

                worker = AsyncDiagnosticLog(Path("unused-test-path"), writer=write)
                try:
                    row = Row(event="sample", value="tiny")
                    reference = weakref.ref(row)
                    self.assertTrue(worker.enqueue([row]))
                    del row
                    self.assertTrue(worker.flush(timeout=2))
                    self.assertEqual(calls, [1])
                    self.assertIsNone(reference())
                    with worker.condition:
                        self.assertEqual(worker.queued_rows, 0)
                        self.assertEqual(worker.write_errors, int(fail))
                        self.assertEqual(worker.dropped, int(fail))
                finally:
                    self.assertTrue(worker.close(timeout=2))

        class StopWorker(BaseException):
            pass

        for fail in (False, True):
            with self.subTest(worker="incident", fail=fail):
                calls = []
                case = self

                class OneItemQueue:
                    gets = 0
                    completed = 0

                    def get(self):
                        self.gets += 1
                        if self.gets == 1:
                            return "private-directory", "incident-id", b'{"tiny":1}'
                        # Observe the real worker at its next blocking boundary.
                        fields = sys._getframe(1).f_locals
                        case.assertIsNone(fields["raw"])
                        case.assertIsNone(fields["root"])
                        case.assertIsNone(fields["incident_id"])
                        case.assertEqual(self.completed, 1)
                        raise StopWorker()

                    def task_done(self):
                        self.completed += 1

                def persist(root, identity, raw):
                    calls.append((root, identity, len(raw)))
                    if fail:
                        raise OSError("bounded test persistence failure")

                queue = OneItemQueue()
                with patch.object(incidents, "_QUEUE", queue), patch.object(
                    incidents, "_persist", persist
                ), patch.object(incidents.LOGGER, "warning") as warning:
                    with self.assertRaises(StopWorker):
                        incidents._writer()
                    self.assertEqual(warning.call_count, int(fail))
                self.assertEqual(calls, [("private-directory", "incident-id", 10)])
                self.assertEqual(queue.completed, 1)


if __name__ == "__main__":
    unittest.main()
