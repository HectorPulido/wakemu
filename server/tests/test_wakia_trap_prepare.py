"""Bounded trap metadata preparation stays advisory and never blocks a turn."""
import json
import time
import unittest
from queue import Empty, Full
from threading import Lock
from unittest.mock import patch

from wakfu_server.wakia_bridge.wakfu_ai.bridge import jondo_trap_prepare as subject


class _Queue:
    def __init__(self, *, full=False):
        self.keys = []
        self.full = full

    def put_nowait(self, key):
        if self.full:
            raise Full
        self.keys.append(key)

    def get_nowait(self):
        if not self.keys:
            raise Empty
        return self.keys.pop(0)

    def task_done(self):
        pass


class TrapPrepareTests(unittest.TestCase):
    def setUp(self):
        self.ready = subject._READY.copy()
        self.pending = subject._PENDING.copy()
        self.failed = subject._FAILED_UNTIL.copy()
        self.started = subject._STARTED
        self.lock = subject._LOCK
        self.queue = subject._QUEUE
        subject._READY.clear()
        subject._PENDING.clear()
        subject._FAILED_UNTIL.clear()
        subject._STARTED = (
            True  # Never start a worker or access catalogs in these tests.
        )
        subject._LOCK = Lock()
        subject._QUEUE = _Queue()
        self.revision = "a" * 64
        self.descriptor = {
            "revision": "published-area-catalog-r1",
            "collection": "documents.native-area-effect-trees.json.effects",
        }
        self.key = (
            self.revision,
            self.descriptor["revision"],
            self.descriptor["collection"],
            1000,
            20,
        )
        self.dto = {
            "version": 1,
            "reference": 1000,
            "level": 20,
            "shape": "cross-h1b1-g1d1",
            "shapeParameters": [1],
            "entryMasks": [10001, 10008],
            "exitMasks": [],
            "areaProperties": [4, 1],
            "roots": [171478, 172568],
            "certainty": "advisory_static_only",
            "effects": [
                {
                    "reference": 171478,
                    "family": 57,
                    "children": [],
                    "criteria": "",
                    "probability": 100,
                    "targets": ["enemy"],
                    "inArea": True,
                    "selector": {"class": "fcE", "mask": 9},
                    "variant": 0,
                    "minimumLevel": 0,
                    "maximumLevel": 32767,
                    "executionMode": 2,
                    "targetMasks": [None] * 7,
                    "timing": {
                        "clock_on_caster": False,
                        "clock_on_target": True,
                        "ryE": 1,
                        "ryF": 0.0,
                        "ryG": False,
                        "ryH": 0,
                        "ryI": 0.0,
                        "esr": True,
                    },
                    "flags": [17],
                    "parameters": [100],
                },
                {
                    "reference": 172568,
                    "family": 5,
                    "children": [],
                    "criteria": "",
                    "probability": 100,
                    "targets": ["ally", "enemy", "self"],
                    "inArea": True,
                    "selector": {"class": "fcE", "mask": 1},
                    "variant": 0,
                    "minimumLevel": 0,
                    "maximumLevel": 32767,
                    "executionMode": 2,
                    "targetMasks": [None] * 7,
                    "timing": {
                        "clock_on_caster": False,
                        "clock_on_target": True,
                        "ryE": 0,
                        "ryF": 0.0,
                        "ryG": False,
                        "ryH": 0,
                        "ryI": 0.0,
                        "esr": False,
                    },
                    "flags": [22],
                    "parameters": [17],
                },
            ],
        }

    def tearDown(self):
        subject._READY.clear()
        subject._READY.update(self.ready)
        subject._PENDING.clear()
        subject._PENDING.update(self.pending)
        subject._FAILED_UNTIL.clear()
        subject._FAILED_UNTIL.update(self.failed)
        subject._STARTED = self.started
        subject._LOCK = self.lock
        subject._QUEUE = self.queue

    def test_cache_miss_schedules_once_without_waiting_and_cache_hit_preserves_rows(
        self,
    ):
        start = time.monotonic()
        self.assertIsNone(
            subject.get_or_schedule(self.revision, self.descriptor, 1000, 20)
        )
        self.assertLess(time.monotonic() - start, 0.2)
        self.assertEqual(subject._QUEUE.keys, [self.key])
        self.assertEqual(subject._PENDING, {self.key})

        subject._PENDING.clear()
        subject._READY[self.key] = json.dumps(self.dto)
        prepared = subject.get_or_schedule(self.revision, self.descriptor, 1000, 20)
        self.assertEqual(prepared, self.dto)
        prepared["effects"].clear()
        self.assertEqual(
            json.loads(subject._READY[self.key])["effects"], self.dto["effects"]
        )

    def test_pending_request_is_deduplicated(self):
        self.assertIsNone(
            subject.get_or_schedule(self.revision, self.descriptor, 1000, 20)
        )
        self.assertIsNone(
            subject.get_or_schedule(self.revision, self.descriptor, 1000, 20)
        )
        self.assertEqual(subject._QUEUE.keys, [self.key])

    def test_worker_start_failure_drains_pending_job_and_allows_retry(self):
        subject._STARTED = False
        with patch.object(
            subject, "Thread", side_effect=RuntimeError("thread unavailable")
        ):
            self.assertFalse(subject.start_worker())
        self.assertNotIn(self.key, subject._PENDING)
        self.assertFalse(subject._STARTED)
        self.assertEqual(subject._QUEUE.keys, [])

    def test_worker_starts_only_by_explicit_startup_call_and_is_idempotent(self):
        subject._STARTED = False
        worker = type("Worker", (), {"start": lambda self: None})()
        with patch.object(subject, "Thread", return_value=worker) as thread:
            self.assertTrue(subject.start_worker())
            self.assertTrue(subject.start_worker())
        thread.assert_called_once()

    def test_turn_request_does_not_start_an_inactive_worker(self):
        subject._STARTED = False
        start = time.monotonic()
        self.assertIsNone(
            subject.get_or_schedule(self.revision, self.descriptor, 1000, 20)
        )
        self.assertLess(time.monotonic() - start, 0.2)
        self.assertEqual(subject._QUEUE.keys, [])
        self.assertNotIn(self.key, subject._PENDING)

    def test_catalog_revision_isolation_and_expired_failure_retry(self):
        subject._READY[self.key] = json.dumps(self.dto)
        changed = dict(self.descriptor, revision="published-area-catalog-r2")
        changed_key = (
            self.revision,
            changed["revision"],
            changed["collection"],
            1000,
            20,
        )
        subject._FAILED_UNTIL[changed_key] = time.monotonic() - 1
        self.assertIsNone(subject.get_or_schedule(self.revision, changed, 1000, 20))
        self.assertEqual(subject._QUEUE.keys, [changed_key])
        self.assertEqual(subject._READY[self.key], json.dumps(self.dto))

    def test_future_failure_throttles_and_full_queue_drops_work_safely(self):
        subject._FAILED_UNTIL[self.key] = time.monotonic() + 30
        self.assertIsNone(
            subject.get_or_schedule(self.revision, self.descriptor, 1000, 20)
        )
        self.assertEqual(subject._QUEUE.keys, [])

        subject._FAILED_UNTIL.clear()
        subject._QUEUE = _Queue(full=True)
        self.assertIsNone(
            subject.get_or_schedule(self.revision, self.descriptor, 1000, 20)
        )
        self.assertNotIn(self.key, subject._PENDING)

    def test_contended_cache_lock_returns_immediately(self):
        subject._LOCK.acquire()
        try:
            start = time.monotonic()
            self.assertIsNone(
                subject.get_or_schedule(self.revision, self.descriptor, 1000, 20)
            )
            self.assertLess(time.monotonic() - start, 0.2)
            self.assertEqual(subject._QUEUE.keys, [])
        finally:
            subject._LOCK.release()


if __name__ == "__main__":
    unittest.main()
