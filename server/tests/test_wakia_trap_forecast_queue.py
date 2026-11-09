"""Nonblocking cache/queue boundary for optional native trap forecasts."""
import queue
import sys
import time
import unittest
from threading import BoundedSemaphore, Lock
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import patch

from wakfu_server.wakia_bridge.wakfu_ai.bridge import jondo_trap_forecast as subject


class _Event:
    def __init__(self):
        self.waits = []
        self.sets = 0
        self.clears = 0

    def wait(self, timeout=None):
        self.waits.append(timeout)
        return False

    def set(self):
        self.sets += 1

    def clear(self):
        self.clears += 1


class TrapForecastQueueTests(unittest.TestCase):
    def setUp(self):
        self.ready = subject._READY.copy()
        self.started = subject._STARTED
        self.lock = subject._LOCK
        self.slot = subject._SLOT
        self.jobs = subject._QUEUE
        self.inflight = subject._INFLIGHT
        self.done = subject._DONE
        subject._READY.clear()
        subject._STARTED = True
        subject._LOCK = Lock()
        subject._SLOT = BoundedSemaphore(1)
        subject._QUEUE = queue.Queue(maxsize=1)
        subject._INFLIGHT = None
        subject._DONE = _Event()
        self.job = {
            "fightInstanceId": "fight-1",
            "turnId": 12,
            "actorId": 7,
            "nativeIdentity": "identity",
            "catalogRevision": "catalog-1",
            "catalogGeneration": "generation-1",
            "catalogCollection": "effects-v1",
            "areaReference": 1000,
            "spellId": 5552,
            "grade": 100,
            "fromCell": 10,
            "aimCell": 15,
            "triggerActorId": 9,
            "triggerCell": 20,
            "origin": (0, 0, 0),
            "aim": (1, 0, 0),
            "triggerOrigin": (2, 0, 0),
            "triggerCellXYZ": (3, 0, 0),
        }
        self.key = subject._key(self.job)
        current = type("Current", (), {"id": 7, "position": (0, 0, 0)})()
        fight = type("Fight", (), {"current": current, "turn_id": 12})()
        self.oracle = type(
            "Oracle",
            (),
            {
                "runtime": type(
                    "Runtime", (), {"fight": fight, "tactical_encounter_id": "fight-1"}
                )()
            },
        )()

    def tearDown(self):
        subject._READY.clear()
        subject._READY.update(self.ready)
        subject._STARTED = self.started
        subject._LOCK = self.lock
        subject._SLOT = self.slot
        subject._QUEUE = self.jobs
        subject._INFLIGHT = self.inflight
        subject._DONE = self.done

    def test_fresh_cache_hit_and_stale_cache_fallback(self):
        result = {"complete": False, "deltas": []}
        subject._READY[self.key] = (time.monotonic(), result)
        with patch.object(
            subject, "detached_oracle", side_effect=AssertionError("cache hit copied")
        ):
            self.assertIs(subject.get_or_schedule(self.oracle, self.job), result)

        subject._READY[self.key] = (time.monotonic() - 6, result)
        with patch.object(subject, "detached_oracle", return_value="private"):
            self.assertIsNone(subject.get_or_schedule(self.oracle, self.job))
        queued_key, private, job = subject._QUEUE.get_nowait()
        self.assertEqual(queued_key, self.key)
        self.assertEqual(private, "private")
        self.assertEqual(job, self.job)
        self.assertIsNot(job, self.job)

    def test_inactive_worker_lock_contention_and_busy_slot_fall_back_without_copy(self):
        subject._STARTED = False
        with patch.object(
            subject,
            "detached_oracle",
            side_effect=AssertionError("inactive worker copied"),
        ):
            self.assertIsNone(subject.get_or_schedule(self.oracle, self.job))

        subject._STARTED = True
        subject._LOCK.acquire()
        try:
            with patch.object(
                subject,
                "detached_oracle",
                side_effect=AssertionError("locked request copied"),
            ):
                self.assertIsNone(subject.get_or_schedule(self.oracle, self.job))
        finally:
            subject._LOCK.release()

        # Reserve the only slot and prove a second request does no expensive copy.
        self.assertTrue(subject._SLOT.acquire(blocking=False))
        try:
            with patch.object(
                subject,
                "detached_oracle",
                side_effect=AssertionError("busy slot copied"),
            ):
                self.assertIsNone(subject.get_or_schedule(self.oracle, self.job))
        finally:
            subject._SLOT.release()

    def test_copy_or_queue_failure_releases_reserved_slot(self):
        with patch.object(
            subject, "detached_oracle", side_effect=ValueError("not detachable")
        ):
            self.assertIsNone(subject.get_or_schedule(self.oracle, self.job))
        self.assertTrue(subject._SLOT.acquire(blocking=False))
        subject._SLOT.release()

    def test_ready_wait_is_bounded_and_only_waits_for_identical_inflight_key(self):
        subject._INFLIGHT = self.key
        self.assertIsNone(subject.get_ready(self.job))
        self.assertEqual(subject._DONE.waits, [])
        self.assertIsNone(subject.get_ready(self.job, wait_ms=50))
        self.assertEqual(subject._DONE.waits, [0.05])

        subject._DONE.waits.clear()
        subject._INFLIGHT = ("other-job",)
        self.assertIsNone(subject.get_ready(self.job, wait_ms=50))
        self.assertEqual(subject._DONE.waits, [])

        subject._INFLIGHT = self.key
        self.assertIsNone(subject.get_ready(self.job, wait_ms=51))
        self.assertEqual(subject._DONE.waits, [])

        subject._QUEUE = queue.Queue(maxsize=1)
        subject._QUEUE.put_nowait(("occupied", None, {}))
        with patch.object(subject, "detached_oracle", return_value="private"):
            self.assertIsNone(subject.get_or_schedule(self.oracle, self.job))
        self.assertTrue(subject._SLOT.acquire(blocking=False))
        subject._SLOT.release()

    def test_forecast_rejects_branch_crossing_timeline_round(self):
        actor = NS(id=7, position=(0, 0, 0), hp=100, mp=3)
        target = NS(id=9, position=(2, 0, 0), hp=100, mp=2)
        area = {1000: {"native_area_contract": "fbc", "owner_id": 7, "reference": 1000}}

        def move(_owner, _identity, _path, *, step_callback):
            step_callback(end_fight, target, (1, 0, 0), (2, 0, 0))

        end_fight = NS(
            current=target,
            actors={7: actor, 9: target},
            native_effect_areas=area,
            move=move,
        )

        class Fight:
            current = actor
            native_effect_areas = {}

            def move(self, _owner, _identity, _path, *, step_callback):
                step_callback(self, target, (1, 0, 0), (2, 0, 0))

        runtime = NS(fight=Fight())

        class Oracle:
            def __init__(self):
                self.runtime = runtime
                self.action = 0

            def preview(self, _runtime, _request):
                self.action += 1
                if self.action == 1:
                    return (
                        NS(fight=NS(native_effect_areas=area), action_id=40),
                        None,
                        None,
                    )
                return NS(fight=end_fight, action_id=41), None, None

        native_catalog = NS(release=lambda: "catalog-r")
        publication = object()
        modules = {
            "wakfu_server.wakia_bridge.wakfu_ai.native.native_control": ModuleType(
                "native_control"
            ),
            "wakfu_server.combat_additional_turn": ModuleType("combat_additional_turn"),
            "wakfu_server.native_compiled_catalog": ModuleType(
                "native_compiled_catalog"
            ),
        }
        modules[
            "wakfu_server.wakia_bridge.wakfu_ai.native.native_control"
        ].effective_input_owner = lambda *_: 9
        modules[
            "wakfu_server.wakia_bridge.wakfu_ai.native.native_control"
        ].effective_server_controlled = lambda *_: False
        modules["wakfu_server.combat_additional_turn"].timeline_round = lambda _fight: 4
        modules[
            "wakfu_server.native_compiled_catalog"
        ].resolve_publication = lambda **_kwargs: publication
        modules[
            "wakfu_server.native_compiled_catalog"
        ].descriptor_for = lambda *_args: {"revision": "generation-g"}
        mismatch = {
            "observed": {"timelineRoundBefore": 4, "timelineRoundAfter": 5},
            "control": {"timelineRoundBefore": 4, "timelineRoundAfter": 4},
        }
        job = {
            "catalogRevision": "catalog-r",
            "catalogCollection": "areas",
            "catalogGeneration": "generation-g",
            "actorId": 7,
            "origin": (0, 0, 0),
            "spellId": 5552,
            "grade": 100,
            "aim": (1, 0, 0),
            "areaReference": 1000,
            "triggerActorId": 9,
            "triggerOrigin": (2, 0, 0),
            "triggerCellXYZ": (3, 0, 0),
            "livingActorIds": [7, 9],
            "nativeIdentity": "identity",
            "fightInstanceId": "fight",
            "turnId": 12,
            "fromCell": 10,
            "aimCell": 11,
            "triggerCell": 12,
        }
        with patch.dict(sys.modules, modules), patch.object(
            subject, "compare_area_movement", return_value=mismatch
        ):
            import wakfu_server

            with patch.object(
                wakfu_server, "native_catalog", native_catalog, create=True
            ):
                self.assertIsNone(subject._forecast(Oracle(), job))


if __name__ == "__main__":
    unittest.main()
