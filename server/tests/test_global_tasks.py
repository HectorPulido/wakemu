import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from postgres_case import PostgresCase
import urllib.request
import urllib.error
from wakfu_server.global_tasks import GlobalTasks, SlowSaveAnnouncements
from wakfu_server.api import serve_api
from wakfu_server.world_scheduler import MemoryBackend, Scheduler


class GlobalTaskTests(PostgresCase):
    class ManualTimer:
        instances = []

        def __init__(self, _delay, callback, *, args=()):
            self.callback = callback
            self.args = args
            self.daemon = False
            self.cancelled = False
            type(self).instances.append(self)

        def start(self):
            pass

        def cancel(self):
            self.cancelled = True

        def fire(self):
            # Calling a canceled callback models a timer that was already
            # queued when a fast flush completed.
            self.callback(*self.args)

    def setUp(self):
        super().setUp()
        self.ManualTimer.instances = []

    def test_fast_flush_stays_silent_even_if_canceled_timer_wakes_late(self):
        messages = []
        world = type(
            "World",
            (),
            {"information_all": lambda _self, text: messages.append(text) or 1},
        )()
        announce = SlowSaveAnnouncements(
            world, threshold_seconds=1, timer_factory=self.ManualTimer
        )
        tasks = GlobalTasks({"positions_flush": lambda: None}, observer=announce)

        tasks.run("positions_flush", "positions_flush:fast")
        self.assertEqual(1, len(self.ManualTimer.instances))
        self.assertTrue(self.ManualTimer.instances[0].cancelled)
        self.ManualTimer.instances[0].fire()
        self.assertEqual([], messages)

    def test_slow_flush_announces_start_then_completion(self):
        entered = threading.Event()
        release = threading.Event()
        messages = []

        def callback():
            entered.set()
            self.assertTrue(release.wait(2))

        world = type(
            "World",
            (),
            {"information_all": lambda _self, text: messages.append(text) or 1},
        )()
        announce = SlowSaveAnnouncements(
            world, threshold_seconds=1, timer_factory=self.ManualTimer
        )
        tasks = GlobalTasks({"positions_flush": callback}, observer=announce)
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(tasks.run, "positions_flush", "positions_flush:slow")
            self.assertTrue(entered.wait(2))
            self.ManualTimer.instances[0].fire()
            release.set()
            self.assertEqual("completed", result.result(2)["status"])
        self.assertEqual([announce.STARTED_TEXT, announce.COMPLETED_TEXT], messages)

    def test_slow_flush_failure_announces_failure_not_completion(self):
        entered = threading.Event()
        release = threading.Event()
        messages = []

        def callback():
            entered.set()
            self.assertTrue(release.wait(2))
            raise RuntimeError("private error")

        world = type(
            "World",
            (),
            {"information_all": lambda _self, text: messages.append(text) or 1},
        )()
        announce = SlowSaveAnnouncements(
            world, threshold_seconds=1, timer_factory=self.ManualTimer
        )
        tasks = GlobalTasks({"positions_flush": callback}, observer=announce)
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(
                tasks.run, "positions_flush", "positions_flush:slow-fail"
            )
            self.assertTrue(entered.wait(2))
            self.ManualTimer.instances[0].fire()
            release.set()
            with self.assertRaisesRegex(RuntimeError, "private error"):
                result.result(2)
        self.assertEqual([announce.STARTED_TEXT, announce.FAILED_TEXT], messages)
        self.assertNotIn(announce.COMPLETED_TEXT, messages)

    def test_finish_waits_for_inflight_start_delivery_before_announcement(self):
        entered = threading.Event()
        release_send = threading.Event()
        release_callback = threading.Event()
        messages = []

        def deliver(text):
            messages.append(text)
            if text == SlowSaveAnnouncements.STARTED_TEXT:
                entered.set()
                self.assertTrue(release_send.wait(2))
            return 1

        def callback():
            self.assertTrue(release_callback.wait(2))

        world = type(
            "World", (), {"information_all": lambda _self, text: deliver(text)}
        )()
        announce = SlowSaveAnnouncements(
            world, threshold_seconds=1, timer_factory=self.ManualTimer
        )
        tasks = GlobalTasks({"positions_flush": callback}, observer=announce)
        with ThreadPoolExecutor(max_workers=3) as pool:
            result = pool.submit(tasks.run, "positions_flush", "positions_flush:race")
            self.assertTrue(announce.pending or result.running())
            # Wait until GlobalTasks has dispatched its started observer and
            # the manual timer is registered.
            for _ in range(200):
                if self.ManualTimer.instances:
                    break
                threading.Event().wait(0.005)
            timer = self.ManualTimer.instances[0]
            start_delivery = pool.submit(timer.fire)
            self.assertTrue(entered.wait(2))
            release_callback.set()
            # The task cannot announce completion ahead of the in-flight start.
            threading.Event().wait(0.02)
            self.assertEqual([SlowSaveAnnouncements.STARTED_TEXT], messages)
            release_send.set()
            start_delivery.result(2)
            self.assertEqual("completed", result.result(2)["status"])
        self.assertEqual(
            [SlowSaveAnnouncements.STARTED_TEXT, SlowSaveAnnouncements.COMPLETED_TEXT],
            messages,
        )

    def test_whitelist_occurrence_and_failed_retry(self):
        with self.assertRaises(ValueError):
            GlobalTasks({"arbitrary_weather": lambda: None})
        calls = []

        def callback():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("storage unavailable")

        tasks = GlobalTasks({"positions_flush": callback})
        with self.assertRaises(ValueError):
            tasks.run("positions_flush", "builds_flush:1")
        with self.assertRaises(RuntimeError):
            tasks.run("positions_flush", "positions_flush:1")
        self.assertFalse(
            tasks.run("positions_flush", "positions_flush:1")["deduplicated"]
        )
        self.assertTrue(
            tasks.run("positions_flush", "positions_flush:1")["deduplicated"]
        )
        self.assertEqual(len(calls), 2)

    def test_observer_announces_one_start_and_completion_for_duplicate_occurrence(self):
        events = []
        calls = []
        tasks = GlobalTasks(
            {"positions_flush": lambda: calls.append("flush")},
            observer=lambda event: events.append(dict(event)),
        )

        first = tasks.run("positions_flush", "positions_flush:save-1")
        replay = tasks.run("positions_flush", "positions_flush:save-1")

        self.assertFalse(first["deduplicated"])
        self.assertTrue(replay["deduplicated"])
        self.assertEqual(["flush"], calls)
        self.assertEqual(
            ["started", "completed"], [event["status"] for event in events]
        )
        self.assertTrue(
            all(event["request_id"] == "positions_flush:save-1" for event in events)
        )

    def test_failure_is_announced_once_and_never_marked_completed(self):
        events = []
        calls = []

        def callback():
            calls.append("flush")
            if len(calls) == 1:
                raise RuntimeError("private internal detail")

        tasks = GlobalTasks({"positions_flush": callback}, observer=events.append)
        with self.assertRaisesRegex(RuntimeError, "private internal detail"):
            tasks.run("positions_flush", "positions_flush:save-2")
        self.assertEqual("failed", events[-1]["status"])
        self.assertNotIn("error", events[-1])
        self.assertNotIn("error_message", events[-1])

        successful_retry = tasks.run("positions_flush", "positions_flush:save-2")
        duplicate = tasks.run("positions_flush", "positions_flush:save-2")
        self.assertFalse(successful_retry["deduplicated"])
        self.assertTrue(duplicate["deduplicated"])
        self.assertEqual(
            ["started", "failed", "started", "completed"],
            [e["status"] for e in events],
        )
        self.assertEqual(2, len(calls))

    def test_fast_failure_then_slow_retry_can_announce_its_own_attempt(self):
        calls = []
        messages = []
        entered = threading.Event()
        release = threading.Event()

        def callback():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("fast failure")
            entered.set()
            self.assertTrue(release.wait(2))

        world = type(
            "World",
            (),
            {"information_all": lambda _self, text: messages.append(text) or 1},
        )()
        announce = SlowSaveAnnouncements(
            world, threshold_seconds=1, timer_factory=self.ManualTimer
        )
        tasks = GlobalTasks({"positions_flush": callback}, observer=announce)
        with self.assertRaisesRegex(RuntimeError, "fast failure"):
            tasks.run("positions_flush", "positions_flush:retry-slow")
        self.assertEqual([], messages)

        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(
                tasks.run, "positions_flush", "positions_flush:retry-slow"
            )
            self.assertTrue(entered.wait(2))
            self.ManualTimer.instances[1].fire()
            release.set()
            self.assertEqual("completed", result.result(2)["status"])
        self.assertEqual([announce.STARTED_TEXT, announce.COMPLETED_TEXT], messages)

    def test_observer_failure_does_not_change_flush_result(self):
        calls = []

        def observer(_event):
            raise OSError("notification peer failed")

        tasks = GlobalTasks(
            {"positions_flush": lambda: calls.append(1)}, observer=observer
        )
        result = tasks.run("positions_flush", "positions_flush:save-3")
        self.assertEqual("completed", result["status"])
        self.assertEqual([1], calls)

    def test_concurrent_same_occurrence_runs_flush_once_and_notifies_once(self):
        entered = threading.Event()
        release = threading.Event()
        events = []
        calls = []

        def callback():
            calls.append(1)
            entered.set()
            self.assertTrue(release.wait(2))

        tasks = GlobalTasks({"positions_flush": callback}, observer=events.append)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(tasks.run, "positions_flush", "positions_flush:save-4")
            self.assertTrue(entered.wait(2))
            second = pool.submit(tasks.run, "positions_flush", "positions_flush:save-4")
            release.set()
            first_result, second_result = first.result(2), second.result(2)
        self.assertEqual(1, len(calls))
        self.assertEqual(
            1, sum(not r["deduplicated"] for r in (first_result, second_result))
        )
        self.assertEqual(["started", "completed"], [e["status"] for e in events])

    def test_http_global_without_session_and_scheduler_deduplication(self):
        store = self.store
        account = store.register("scheduler", "password")["id"]
        token = store.issue_token(account, "scheduler")
        calls = []
        callbacks = GlobalTasks({"positions_flush": lambda: calls.append(1)})
        ready = threading.Event()
        servers = []

        def on_ready(server):
            servers.append(server)
            ready.set()

        thread = threading.Thread(
            target=serve_api,
            args=(store, "127.0.0.1", 0),
            kwargs=dict(global_tasks=callbacks, on_ready=on_ready),
            daemon=True,
        )
        thread.start()
        self.assertTrue(ready.wait(3))
        base = "http://127.0.0.1:%s" % servers[0].server_port

        def action(occurrence, lost):
            req = urllib.request.Request(
                base + "/test/tasks/positions_flush",
                data=json.dumps({"request_id": occurrence}).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + token,
                },
            )
            with urllib.request.urlopen(req, timeout=2) as response:
                self.assertEqual(json.load(response)["status"], "completed")

        try:
            backend = MemoryBackend(lambda: 1200)
            scheduler = Scheduler(
                backend,
                {"positions_flush": dict(interval=1200, action=action)},
                clock=lambda: 1200,
            )
            self.assertTrue(scheduler.tick()[0]["success"])
            self.assertEqual(scheduler.tick(), [])
            action("positions_flush:1", threading.Event())
            self.assertEqual(calls, [1])
            with urllib.request.urlopen(
                urllib.request.Request(
                    base + "/test/tasks", headers={"Authorization": "Bearer " + token}
                )
            ) as response:
                self.assertEqual(
                    json.load(response),
                    [{"name": "positions_flush", "scope": "global"}],
                )
        finally:
            servers[0].shutdown()
            servers[0].server_close()
            thread.join(2)


class GlobalTaskCacheTests(unittest.TestCase):
    def test_expiration_and_capacity_evict_only_old_completed_occurrences(self):
        now = [0]
        calls = []
        events = []
        tasks = GlobalTasks(
            {"positions_flush": lambda: calls.append(1)},
            clock=lambda: now[0],
            retention_seconds=5,
            max_cached_occurrences=2,
            observer=events.append,
        )
        for suffix in ("a", "b", "c"):
            tasks.run("positions_flush", "positions_flush:" + suffix)
        self.assertEqual(2, len(tasks.completed))
        self.assertEqual(2, len(tasks.announced))
        self.assertNotIn(("positions_flush", "positions_flush:a"), tasks.completed)
        self.assertTrue(
            tasks.run("positions_flush", "positions_flush:c")["deduplicated"]
        )
        now[0] = 5
        self.assertFalse(
            tasks.run("positions_flush", "positions_flush:c")["deduplicated"]
        )
        self.assertEqual(4, len(calls))
        self.assertEqual(1, len(tasks.completed))
        self.assertEqual(1, len(tasks.announced))
        self.assertEqual({}, tasks.active_announced)

    def test_running_occurrence_survives_expiration_and_capacity_pressure(self):
        now = [0]
        entered, release = threading.Event(), threading.Event()
        calls, events = [], []

        def callback():
            calls.append(1)
            if threading.current_thread().name.startswith("blocked"):
                entered.set()
                self.assertTrue(release.wait(3))

        tasks = GlobalTasks(
            {"positions_flush": callback},
            clock=lambda: now[0],
            retention_seconds=1,
            max_cached_occurrences=1,
            observer=events.append,
        )
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="blocked") as pool:
            first = pool.submit(tasks.run, "positions_flush", "positions_flush:active")
            self.assertTrue(entered.wait(2))
            now[0] = 10
            for suffix in ("a", "b", "c"):
                tasks.run("positions_flush", "positions_flush:" + suffix)
            second = pool.submit(tasks.run, "positions_flush", "positions_flush:active")
            release.set()
            results = [first.result(2), second.result(2)]
        self.assertEqual(4, len(calls))
        self.assertEqual(1, sum(r["deduplicated"] for r in results))
        self.assertEqual(
            ["started", "completed"],
            [
                e["status"]
                for e in events
                if e["request_id"] == "positions_flush:active"
            ],
        )
        self.assertFalse(tasks.running)
        self.assertFalse(tasks.active_announced)
        self.assertLessEqual(len(tasks.completed), 1)
        self.assertLessEqual(len(tasks.announced), 1)

    def test_invalid_cache_settings_are_rejected(self):
        for retention in (0, -1, True, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                GlobalTasks({}, retention_seconds=retention)
        for capacity in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                GlobalTasks({}, max_cached_occurrences=capacity)
