"""Best-effort socket maintenance preserves authoritative cooldown drains."""
import math
import threading
from types import SimpleNamespace
import unittest

from wakfu_server.monster_collect import Harvests, availability_packet


class AvailabilityContentionTests(unittest.TestCase):
    def test_busy_maintenance_returns_without_changing_due_cooldown(self):
        harvest = Harvests(SimpleNamespace(clock=lambda: 100.0))
        key = (1, 0, -10, 1)
        harvest.regenerating[key] = 90.0
        harvest.next_regeneration = 90.0
        held, release = threading.Event(), threading.Event()

        def holder():
            with harvest.lock:
                held.set()
                release.wait(5)

        thread = threading.Thread(target=holder)
        thread.start()
        self.assertTrue(held.wait(2))
        try:
            self.assertEqual(harvest.due_availability(blocking=False), [])
            self.assertEqual(harvest.regenerating, {key: 90.0})
            self.assertEqual(harvest.next_regeneration, 90.0)
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(
            harvest.due_availability(blocking=False),
            [
                (1, 0, availability_packet(-10, 1, True)),
            ],
        )
        self.assertEqual(harvest.due_availability(blocking=False), [])
        self.assertEqual(harvest.next_regeneration, math.inf)

    def test_request_mutator_still_waits_and_keeps_occupation_until_lock_release(self):
        harvest = Harvests(SimpleNamespace(clock=lambda: 100.0))
        ticket = {"generation": "owner", "monster_id": -10}
        harvest.pending[1] = ticket
        harvest.targets[-10] = 1
        started, finished = threading.Event(), threading.Event()
        result = []

        def cancel():
            started.set()
            result.append(harvest.cancel(1, "owner"))
            finished.set()

        with harvest.lock:
            thread = threading.Thread(target=cancel)
            thread.start()
            self.assertTrue(started.wait(2))
            self.assertFalse(finished.wait(0.05))
            self.assertIs(harvest.pending[1], ticket)
            self.assertEqual(harvest.targets[-10], 1)
        thread.join(2)
        self.assertTrue(finished.is_set())
        self.assertEqual(result, [True])
        self.assertEqual(harvest.pending, {})
        self.assertEqual(harvest.targets, {})
