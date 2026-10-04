import threading
import unittest
from wakfu_server.world_scheduler import Scheduler, MemoryBackend


class SchedulerTests(unittest.TestCase):
    def test_completion_deduplicates_and_next_interval_runs(self):
        now = [100.0]
        backend = MemoryBackend(lambda: now[0])
        calls = []
        task = {
            "interval": 10,
            "action": lambda occurrence, lost: calls.append(occurrence),
        }
        a = Scheduler(backend, {"world": task}, clock=lambda: now[0])
        b = Scheduler(backend, {"world": task}, clock=lambda: now[0])
        self.assertTrue(a.tick()[0]["success"])
        self.assertEqual(b.tick(), [])
        now[0] = 110.0
        b.tick()
        self.assertEqual(calls, ["world:10", "world:11"])

    def test_retry_delay_limit_and_stable_occurrence(self):
        now = [100.0]
        backend = MemoryBackend(lambda: now[0])
        calls = []

        def fail(occurrence, lost):
            calls.append(occurrence)
            raise ValueError("retry")

        scheduler = Scheduler(
            backend,
            {
                "job": {
                    "interval": 100,
                    "retry_seconds": 2,
                    "max_attempts": 2,
                    "action": fail,
                }
            },
            clock=lambda: now[0],
        )
        self.assertFalse(scheduler.tick()[0]["success"])
        self.assertEqual(scheduler.tick(), [])
        now[0] = 102.0
        scheduler.tick()
        now[0] = 104.0
        self.assertEqual(scheduler.tick(), [])
        self.assertEqual(calls, ["job:1", "job:1"])

    def test_overlapping_worker_and_expired_fencing(self):
        now = [10.0]
        backend = MemoryBackend(lambda: now[0])
        self.assertTrue(backend.claim("job", "job:1", "old", 3))
        self.assertFalse(backend.claim("job", "job:2", "other", 3))
        now[0] = 14.0
        self.assertTrue(backend.claim("job", "job:2", "new", 3))
        self.assertFalse(
            backend.finish("job", "job:1", "old", success=True, delay=1, retention=60)
        )
        self.assertTrue(
            backend.finish("job", "job:2", "new", success=True, delay=1, retention=60)
        )
