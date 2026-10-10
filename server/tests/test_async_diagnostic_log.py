"""Concurrency and retention behavior for the bounded diagnostic writer."""
import threading
import time
import unittest

from wakfu_server.async_diagnostic_log import AsyncDiagnosticLog


class AsyncDiagnosticLogTests(unittest.TestCase):
    def make_log(self, writer, *, capacity=16, critical_reserve=2):
        log = AsyncDiagnosticLog(
            None,
            capacity=capacity,
            critical_reserve=critical_reserve,
            writer=writer,
        )

        def cleanup():
            unblock = getattr(writer, "unblock", None)
            if unblock is not None:
                unblock.set()
            log.close(timeout=2)

        self.addCleanup(cleanup)
        return log

    def test_blocked_writer_does_not_slow_enqueue_or_an_unrelated_lease_lock(self):
        entered, unblock = threading.Event(), threading.Event()

        def writer(rows):
            entered.set()
            if not unblock.wait(2):
                raise TimeoutError("test did not release diagnostic writer")

        writer.unblock = unblock
        log = self.make_log(writer)
        self.assertTrue(log.enqueue([{"event": "first"}]))
        self.assertTrue(entered.wait(1), "writer did not start")

        started = time.monotonic()
        self.assertTrue(log.enqueue([{"event": "queued"}]))
        self.assertLess(time.monotonic() - started, 0.1)

        lease_lock = threading.Lock()
        lease_lock.acquire()
        acquired = threading.Event()

        def acquire_lease():
            with lease_lock:
                acquired.set()

        lease = threading.Thread(target=acquire_lease, daemon=True)
        lease.start()
        lease_lock.release()
        self.assertTrue(acquired.wait(0.2), "unrelated lease lock stayed unavailable")
        unblock.set()
        lease.join(1)
        self.assertTrue(log.flush(1))

    def test_critical_reserve_evicts_noncritical_rows_and_reports_overflow(self):
        entered, unblock = threading.Event(), threading.Event()
        writes = []

        def writer(rows):
            if not writes:
                entered.set()
                if not unblock.wait(2):
                    raise TimeoutError("test did not release diagnostic writer")
            writes.append(tuple(rows))

        writer.unblock = unblock
        log = self.make_log(writer, capacity=4, critical_reserve=1)
        self.assertTrue(log.enqueue([{"event": "active"}]))
        self.assertTrue(entered.wait(1), "writer did not block on first batch")
        self.assertTrue(log.enqueue([{"event": "discarded"}]))
        self.assertTrue(log.enqueue([{"event": "retained_a"}]))
        self.assertTrue(log.enqueue([{"event": "retained_b"}]))
        self.assertTrue(
            log.enqueue([{"event": "checkpoint_failed"}, {"event": "detail"}])
        )
        unblock.set()
        self.assertTrue(log.flush(2))

        self.assertEqual("active", writes[0][0]["event"])
        self.assertEqual(
            ["diagnostic_log_overflow", "retained_a"],
            [row["event"] for row in writes[1]],
        )
        self.assertEqual(1, writes[1][0]["dropped_rows"])
        self.assertEqual(
            ["retained_b", "checkpoint_failed", "detail"],
            [row["event"] for row in writes[2] + writes[3]],
        )

    def test_request_batches_remain_contiguous_in_retained_order(self):
        writes = []
        log = self.make_log(writes.append)
        first = [{"event": "request_a_1"}, {"event": "request_a_2"}]
        second = [{"event": "request_b_1"}, {"event": "request_b_2"}]
        self.assertTrue(log.enqueue(first))
        self.assertTrue(log.enqueue(second))
        self.assertTrue(log.flush(1))
        self.assertEqual([tuple(first), tuple(second)], writes)

    def test_close_timeout_is_bounded_while_writer_is_blocked(self):
        entered, unblock = threading.Event(), threading.Event()

        def writer(rows):
            entered.set()
            if not unblock.wait(2):
                raise TimeoutError("test did not release diagnostic writer")

        writer.unblock = unblock
        log = self.make_log(writer)
        self.assertTrue(log.enqueue([{"event": "pending"}]))
        self.assertTrue(entered.wait(1), "writer did not start")
        started = time.monotonic()
        self.assertFalse(log.close(timeout=0.05))
        self.assertLess(time.monotonic() - started, 0.25)
        unblock.set()
        self.assertTrue(log.close(timeout=1))

    def test_writer_exception_is_contained_and_next_write_reports_loss(self):
        failed, writes = threading.Event(), []

        def writer(rows):
            if not failed.is_set():
                failed.set()
                raise OSError("disk unavailable")
            writes.append(tuple(rows))

        log = self.make_log(writer)
        self.assertTrue(log.enqueue([{"event": "first"}]))
        self.assertTrue(failed.wait(1), "writer did not attempt first batch")
        self.assertTrue(log.enqueue([{"event": "second"}]))
        self.assertTrue(log.flush(1))
        self.assertEqual(
            ["diagnostic_log_overflow", "second"],
            [row["event"] for row in writes[0]],
        )
        self.assertEqual(1, writes[0][0]["dropped_rows"])
        self.assertEqual(1, writes[0][0]["write_errors"])


if __name__ == "__main__":
    unittest.main()
