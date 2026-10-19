"""Deferred completion for transient position-owner contention."""

import unittest

from wakfu_server.position_buffer import PositionOwnerBusy
from wakfu_server.position_lifecycle import PendingPositionReturn


class PendingPositionReturnTests(unittest.TestCase):
    def test_contention_longer_than_previous_timeout_resumes_once(self):
        now = 0.0
        flushes, completions, busy_attempts = [], [], []
        pending = PendingPositionReturn(now=now)

        def flush():
            flushes.append(now)
            if now < 1.2:
                raise PositionOwnerBusy("owner lock held")

        def advance():
            nonlocal now
            now = max(now + 0.1, pending.next_attempt_at)

        for _ in range(20):
            done = pending.attempt(
                now=now,
                flush=flush,
                complete=lambda: completions.append("finished"),
                busy=lambda error, attempt: busy_attempts.append(attempt),
            )
            if done:
                break
            advance()

        self.assertGreaterEqual(now, 1.2)
        self.assertTrue(pending.completed)
        self.assertGreater(len(flushes), 2)
        self.assertEqual(completions, ["finished"])
        self.assertEqual(busy_attempts, list(range(1, len(busy_attempts) + 1)))

        self.assertTrue(
            pending.attempt(
                now=now + 10,
                flush=lambda: flushes.append("unexpected"),
                complete=lambda: completions.append("duplicate"),
                busy=lambda error, attempt: None,
            )
        )
        self.assertNotIn("unexpected", flushes)
        self.assertEqual(completions, ["finished"])

    def test_backoff_suppresses_extra_attempts_within_one_idle_window(self):
        pending = PendingPositionReturn(now=0)
        calls = []

        def busy_flush():
            calls.append("flush")
            raise PositionOwnerBusy("busy")

        attempt = lambda at: pending.attempt(
            now=at,
            flush=busy_flush,
            complete=lambda: None,
            busy=lambda error, number: None,
        )
        self.assertFalse(attempt(0))
        self.assertFalse(attempt(0.05))
        self.assertEqual(calls, ["flush"])
        self.assertFalse(attempt(0.1))
        self.assertEqual(calls, ["flush", "flush"])

    def test_only_position_contention_is_deferred(self):
        pending = PendingPositionReturn(now=0)
        calls, completions = [], []

        def fail():
            calls.append("flush")
            raise ValueError("checkpoint invariant failed")

        with self.assertRaisesRegex(ValueError, "checkpoint invariant failed"):
            pending.attempt(
                now=0,
                flush=fail,
                complete=lambda: completions.append("finished"),
                busy=lambda error, attempt: self.fail("unexpected contention"),
            )

        self.assertEqual(calls, ["flush"])
        self.assertEqual(completions, [])

    def test_completion_is_not_repeated_when_post_flush_step_raises(self):
        pending = PendingPositionReturn(now=0)
        calls = []

        def fail_completion():
            calls.append("complete")
            raise ValueError("post-flush checkpoint failed")

        with self.assertRaisesRegex(ValueError, "post-flush checkpoint failed"):
            pending.attempt(
                now=0,
                flush=lambda: None,
                complete=fail_completion,
                busy=lambda error, attempt: None,
            )

        self.assertTrue(pending.completed)
        self.assertTrue(
            pending.attempt(
                now=1,
                flush=lambda: self.fail("flush repeated"),
                complete=fail_completion,
                busy=lambda error, attempt: None,
            )
        )
        self.assertEqual(calls, ["complete"])


if __name__ == "__main__":
    unittest.main()
