import socket
import sys
import threading
import time
import types
import unittest
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import patch

# The integration target is coordinator fencing, not catalog startup. Keep the
# one unrelated bootstrap dependency inert while importing the real registry.
_bootstrap = types.ModuleType("wakfu_server.combat_bootstrap")


def _placement_positions(*args, **kwargs):
    # Let any later server tests resolve the real implementation lazily.
    from wakfu_server.combat_bootstrap import placement_positions

    return placement_positions(*args, **kwargs)


_bootstrap.placement_positions = _placement_positions
import wakfu_server as _server_package

_previous_bootstrap = getattr(_server_package, "combat_bootstrap", None)
sys.modules["wakfu_server.combat_bootstrap"] = _bootstrap
try:
    from wakfu_server.combat_shared import Registry, Session
    from wakfu_server.combat_state import Actor, Fight
finally:
    sys.modules.pop("wakfu_server.combat_bootstrap", None)
    if _previous_bootstrap is None:
        _server_package.__dict__.pop("combat_bootstrap", None)
    else:
        _server_package.combat_bootstrap = _previous_bootstrap

from wakfu_ai.bridge.world_host import execute
from wakfu_ai.bridge.world_background import BackgroundTurn, admission, schedule
from wakfu_ai.bridge.world_sources import bind_private_sources
from wakfu_server.combat_background_work import BackgroundDiagnostics, BackgroundWork
from wakfu_server.combat_expiration_provider import OwnedExpirationFactory


class WorldBackgroundTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(1, 10, "owner-generation", 1134, 0)
        self.registry = Registry(lambda session: session is self.session)
        player = Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True)
        npc = Actor(-200, 1, (2, 0, 0), 20, 4, 2, 1, 1)
        self.fight = Fight(
            801,
            [player, npc],
            {(x, 0, 0) for x in range(3)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0)}},
        )
        self.fight.phase = "active"
        self.fight.order, self.fight.turn_index = [-200, 10], 0
        self.fight.turn_id = 7
        self.runtime = SimpleNamespace(
            fight=self.fight,
            awaiting_ack=None,
            pending=[],
            turn_start_provider=None,
            turn_end_provider=None,
            stats_serializer=None,
        )
        self.runtime.expiration_runtime_factory = OwnedExpirationFactory(
            characters={10: {"id": 10, "account_id": 1, "map_id": 1134}},
            monsters={-200: {"ref": 553}},
            decks={10: b"deck"},
            actor_id=10,
        )
        self.shared = self.registry.register(
            self.fight, self.session, runtime=self.runtime
        )
        self.adapter = SimpleNamespace(registry=self.registry)
        self.viewer = {"id": 10, "account_id": 1, "map_id": 1134, "future": b"full"}
        self.connection = SimpleNamespace(native_ai_diagnostics=None)
        self.records = []
        self.socket_send_threads = []

    def context(self):
        return dict(
            globals=dict(
                combat_session=self.session,
                COMBAT_SESSIONS=self.adapter,
                refresh_shared_combat=lambda: None,
                drain_shared_combat=lambda: None,
                STORE=object(),
                character=self.viewer,
                TEST_MONSTERS_BY_ID={-200: {"ref": 553}},
                connection=self.connection,
                service="world",
                send=lambda *args: self.socket_send_threads.append(
                    threading.get_ident()
                ),
                record=lambda **fields: self.records.append(fields),
            ),
            scopes=[],
        )

    def test_socket_reader_processes_chat_while_background_planner_is_blocked(self):
        entered, release = threading.Event(), threading.Event()
        planner_threads, socket_send_threads = [], []
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)

        def runner(native, **kwargs):
            planner_threads.append(threading.get_ident())
            self.assertIsNone(kwargs["stats_serializer"])
            self.assertNotIn("connection", kwargs)
            self.assertNotIn("send", kwargs)
            entered.set()
            self.assertTrue(release.wait(2))
            if False:
                yield [], {}

        # This is the reader path: execute schedules and returns, then the
        # same thread continues consuming the socket while native planning waits.
        reader_thread = threading.get_ident()
        list(execute(self.runtime, self.context(), runner))
        self.assertTrue(entered.wait(2))
        # A repeated reader dispatch is deduplicated while the first worker owns
        # the encounter. It must not start a second planner.
        list(execute(self.runtime, self.context(), runner))
        right.sendall(b"chat")
        self.assertEqual(left.recv(4), b"chat")
        self.assertNotEqual(planner_threads[0], reader_thread)
        self.assertEqual(self.socket_send_threads, [])
        self.assertEqual(len(planner_threads), 1)
        self.assertEqual(self.shared.sequence, 0)
        release.set()
        self._wait_for_background()
        self.assertEqual(self.shared.sequence, 0)
        self.assertIs(self.shared.runtime, self.runtime)

    def test_cancelled_blocked_planner_cannot_adopt_candidate(self):
        entered, release = threading.Event(), threading.Event()
        packet = (12588, b"private native publication")

        def runner(native, **kwargs):
            native.fight.actors[10].hp -= 11
            entered.set()
            self.assertTrue(release.wait(2))
            yield [packet], {"action": {"type": "cast"}}

        diagnostics = BackgroundDiagnostics()
        job = BackgroundTurn(
            self.shared,
            self.adapter,
            self.session,
            runner,
            object(),
            self.viewer,
            {-200: {"ref": 553}},
            diagnostics,
        )
        worker = threading.Thread(target=job)
        worker.start()
        self.assertTrue(entered.wait(2))
        claim = self.shared.native_ai_turn_claim
        self.assertIsNotNone(claim)
        job.cancel()
        self.assertIsNone(self.shared.native_ai_turn_claim)
        release.set()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.shared.sequence, 0)
        self.assertEqual(self.shared.fight.actors[10].hp, 60)
        self.assertIs(self.shared.runtime, self.runtime)
        self.assertTrue(all(not pending for pending in self.shared.outboxes.values()))
        self.assertFalse(hasattr(self.shared, "native_npc_retry"))

    def test_background_turn_rejects_stale_expected_turn_and_revoked_lease(self):
        calls = []

        def runner(native, **kwargs):
            calls.append(True)
            yield [(1, b"should not publish")], {"action": {"type": "cast"}}

        stale = BackgroundTurn(
            self.shared,
            self.adapter,
            self.session,
            runner,
            object(),
            self.viewer,
            {-200: {"ref": 553}},
            BackgroundDiagnostics(),
        )
        self.fight.turn_id += 1
        stale()
        self.assertEqual(calls, [])
        self.assertEqual(self.shared.sequence, 0)
        self.fight.turn_id -= 1

        stale_source = BackgroundTurn(
            self.shared,
            self.adapter,
            self.session,
            runner,
            object(),
            self.viewer,
            {-200: {"ref": 553}},
            BackgroundDiagnostics(),
        )
        self.shared.sequence += 1
        stale_source()
        self.shared.sequence -= 1
        self.assertEqual(calls, [])
        self.assertEqual(self.shared.sequence, 0)

        revoked = BackgroundTurn(
            self.shared,
            self.adapter,
            self.session,
            runner,
            object(),
            self.viewer,
            {-200: {"ref": 553}},
            BackgroundDiagnostics(),
        )
        self.registry.disconnect(self.session)
        revoked()
        self.assertEqual(calls, [])
        self.assertEqual(self.shared.sequence, 0)
        self.assertEqual(self.shared.fight.actors[10].hp, 60)

    def test_background_work_rejects_duplicate_and_capacity_without_queueing(self):
        work = BackgroundWork(max_jobs=1)
        self.addCleanup(work.shutdown)
        entered, release = threading.Event(), threading.Event()

        class Operation:
            def cancel(self):
                release.set()

            def __call__(self):
                entered.set()
                release.wait(2)

        first = Operation()
        self.assertEqual(work.submit("first", first), "submitted")
        self.assertTrue(entered.wait(2))
        self.assertEqual(work.submit("first", Operation()), "duplicate")
        self.assertEqual(work.submit("second", Operation()), "capacity")
        self.assertEqual(set(work.jobs), {"first"})
        release.set()
        self._wait_until(lambda: not work.jobs)
        second = Operation()
        release.set()
        self.assertEqual(work.submit("second", second), "submitted")
        self._wait_until(lambda: not work.jobs)

    def test_background_work_runs_three_fights_fifo_with_bounded_saturation(self):
        work = BackgroundWork(max_jobs=3, max_workers=1)
        self.addCleanup(work.shutdown)
        first_started, release_first = threading.Event(), threading.Event()
        order = []

        class FightWork:
            def __init__(self, fight_id):
                self.fight_id = fight_id

            def cancel(self):
                pass

            def __call__(self):
                order.append(self.fight_id)
                if self.fight_id == 1:
                    first_started.set()
                    self.assert_released()

            @staticmethod
            def assert_released():
                if not release_first.wait(2):
                    raise AssertionError("first fight did not release")

        self.assertEqual(work.submit("fight-1", FightWork(1)), "submitted")
        self.assertTrue(first_started.wait(2))
        self.assertEqual(work.submit("fight-2", FightWork(2)), "submitted")
        self.assertEqual(work.submit("fight-3", FightWork(3)), "submitted")
        self.assertEqual(work.submit("fight-4", FightWork(4)), "capacity")
        self.assertEqual(set(work.jobs), {"fight-1", "fight-2", "fight-3"})
        release_first.set()
        self._wait_until(lambda: not work.jobs)
        self.assertEqual(order, [1, 2, 3])

    def test_cancelling_queued_fight_skips_its_operation(self):
        work = BackgroundWork(max_jobs=2, max_workers=1)
        self.addCleanup(work.shutdown)
        running, release = threading.Event(), threading.Event()
        invoked = []

        class Operation:
            def __init__(self, name, *, blocks=False):
                self.name, self.blocks = name, blocks

            def cancel(self):
                pass

            def __call__(self):
                invoked.append(self.name)
                if self.blocks:
                    running.set()
                    if not release.wait(2):
                        raise AssertionError("running fight did not release")

        self.assertEqual(
            work.submit("running", Operation("running", blocks=True)), "submitted"
        )
        self.assertTrue(running.wait(2))
        self.assertEqual(work.submit("queued", Operation("queued")), "submitted")
        self.assertTrue(work.cancel("queued"))
        # Cancellation leaves the bounded slot occupied until FIFO dequeue.
        self.assertIn("queued", work.jobs)
        release.set()
        self._wait_until(lambda: not work.jobs)
        self.assertEqual(invoked, ["running"])

    def test_worker_does_not_inherit_reader_contextvars(self):
        work = BackgroundWork(max_jobs=1)
        self.addCleanup(work.shutdown)
        request_scope = ContextVar("background_test_request_scope", default=None)
        finished = threading.Event()
        observed = []

        class Operation:
            def cancel(self):
                pass

            def __call__(self):
                observed.append(request_scope.get())
                finished.set()

        token = request_scope.set("reader-private-request")
        try:
            self.assertEqual(work.submit("context", Operation()), "submitted")
        finally:
            request_scope.reset(token)
        self.assertTrue(finished.wait(2))
        self._wait_until(lambda: not work.jobs)
        self.assertEqual(observed, [None])

    def test_background_timing_metrics_measure_worker_and_queue_wait_separately(self):
        from wakfu_server.performance_profiler import PROFILER

        work = BackgroundWork(max_jobs=2, max_workers=1)
        self.addCleanup(work.shutdown)
        blocker_started, release_blocker = threading.Event(), threading.Event()
        observations = []
        main_thread = threading.get_ident()

        class Blocker:
            def cancel(self):
                release_blocker.set()

            def __call__(self):
                blocker_started.set()
                if not release_blocker.wait(2):
                    raise AssertionError("metric test blocker did not release")

        self.assertEqual(work.submit("blocker", Blocker()), "submitted")
        self.assertTrue(blocker_started.wait(2))
        job = BackgroundTurn(
            self.shared,
            self.adapter,
            self.session,
            lambda native: self._slow_empty_runner(native),
            object(),
            self.viewer,
            {},
            BackgroundDiagnostics(),
        )
        # A known age makes queue wait measurably distinct from worker runtime.
        job.queued_at = time.monotonic() - 0.04
        with (
            patch.object(
                PROFILER,
                "observe",
                side_effect=lambda name, wall, cpu=None, **kw: observations.append(
                    (threading.get_ident(), name, wall, cpu, kw.get("error", False))
                ),
            ),
            patch(
                "wakfu_ai.bridge.world_background.run_shared_turn",
                side_effect=lambda *args, **kwargs: self._slow_empty_runner(None),
            ),
        ):
            self.assertEqual(work.submit("ai-turn", job), "submitted")
            release_blocker.set()
            self._wait_until(lambda: not work.jobs)
        background = [
            row for row in observations if row[1] == "combat.ai_turn.background"
        ]
        queue_wait = [
            row for row in observations if row[1] == "combat.ai_turn.queue_wait"
        ]
        self.assertEqual(len(background), 1)
        self.assertEqual(len(queue_wait), 1)
        self.assertNotEqual(background[0][0], main_thread)
        self.assertEqual(background[0][0], queue_wait[0][0])
        self.assertGreater(queue_wait[0][2], 0.02)
        self.assertGreaterEqual(background[0][2], 0.01)
        self.assertFalse(background[0][4])

    def test_fast_background_failure_backoff_survives_submission_success_race(self):
        from wakfu_server.combat_turn_guard import run_shared_npc_attempt

        calls = []

        def broken(native, **kwargs):
            calls.append("background")
            raise RuntimeError("bounded private planner failure")
            yield [], {}

        class InlineWork:
            def status(self, key):
                return None

            def submit(self, key, operation):
                operation()
                return "submitted"

        with patch("wakfu_server.combat_background_work.NATIVE_WORK", InlineWork()):
            submitted = run_shared_npc_attempt(
                self.shared,
                lambda: schedule(
                    self.shared,
                    self.adapter,
                    self.session,
                    broken,
                    object(),
                    self.viewer,
                    {},
                    BackgroundDiagnostics(),
                ),
                lambda identity, error: self.fail("worker failure escaped foreground"),
            )
            self.assertTrue(submitted)
            retry = self.shared.native_npc_retry
            self.assertEqual(retry[0], (-200, 7))
            self.assertGreater(retry[1], time.monotonic())
            self.assertEqual(
                schedule(
                    self.shared,
                    self.adapter,
                    self.session,
                    broken,
                    object(),
                    self.viewer,
                    {},
                    BackgroundDiagnostics(),
                ),
                "backoff",
            )
        self.assertEqual(calls, ["background"])

    def test_schedule_deduplicates_fight_and_rejects_capacity_without_queueing(self):
        import wakfu_server.combat_background_work as server_work

        work = BackgroundWork(max_jobs=1)
        self.addCleanup(work.shutdown)
        entered, release = threading.Event(), threading.Event()

        def runner(native, **kwargs):
            entered.set()
            self.assertTrue(release.wait(2))
            if False:
                yield [], {}

        other = WorldBackgroundTests()
        other.setUp()
        with patch.object(server_work, "NATIVE_WORK", work):
            self.assertEqual(
                schedule(
                    self.shared,
                    self.adapter,
                    self.session,
                    runner,
                    object(),
                    self.viewer,
                    {},
                    BackgroundDiagnostics(),
                ),
                "submitted",
            )
            self.assertTrue(entered.wait(2))
            self.assertEqual(
                schedule(
                    self.shared,
                    self.adapter,
                    self.session,
                    runner,
                    object(),
                    self.viewer,
                    {},
                    BackgroundDiagnostics(),
                ),
                "duplicate",
            )
            self.assertEqual(
                schedule(
                    other.shared,
                    other.adapter,
                    other.session,
                    runner,
                    object(),
                    other.viewer,
                    {},
                    BackgroundDiagnostics(),
                ),
                "capacity",
            )
            self.assertEqual(len(work.jobs), 1)
            release.set()
            self._wait_until(lambda: not work.jobs)

    def test_diagnostics_mailbox_is_bounded_and_discards_other_owner_fence(self):
        for invalid in (0, True):
            with self.subTest(capacity=invalid), self.assertRaises(ValueError):
                BackgroundDiagnostics(capacity=invalid)
        mailbox = BackgroundDiagnostics(capacity=2)
        owner = (1, "generation-a", 10)
        other = (2, "generation-b", 20)
        mailbox.put(owner, {"event": "one", "detail": "x" * 1000})
        mailbox.put(other, {"event": "wrong owner"})
        mailbox.put(owner, {"event": "overflow"})
        items, dropped = mailbox.drain(owner)
        self.assertEqual([item["event"] for item in items], ["one"])
        self.assertEqual(len(items[0]["detail"]), 512)
        self.assertEqual(dropped, 1)
        self.assertEqual(mailbox.drain(other), ((), 0))

    def test_old_engine_legacy_rift_and_missing_capability_stay_foreground(self):
        self.assertEqual(admission(self.shared), None)
        self.runtime.expiration_runtime_factory = object()
        self.assertEqual(admission(self.shared), "legacy_lifecycle_providers")
        self.runtime.expiration_runtime_factory = OwnedExpirationFactory(
            characters={10: {"id": 10, "account_id": 1, "map_id": 1134}},
            monsters={},
            decks={10: b"deck"},
            actor_id=10,
        )
        self.fight.rift_wave_state = {"wave": 1}
        self.assertEqual(admission(self.shared), "rift_providers_unqualified")
        del self.fight.rift_wave_state

        clock_calls = []
        self.runtime.clock = lambda: clock_calls.append(True)
        self.assertEqual(admission(self.shared), "custom_clock_unqualified")
        with self.assertRaisesRegex(ValueError, "canonical clock"):
            bind_private_sources(self.runtime, self.session)
        self.assertEqual(clock_calls, [])
        calls = []

        def foreground_clock(native, **kwargs):
            calls.append(threading.get_ident())
            yield [], {"action": {"type": "end_turn"}}

        list(execute(self.runtime, self.context(), foreground_clock))
        self.assertEqual(calls, [threading.get_ident()])
        self.assertEqual(clock_calls, [])
        self.assertIn(
            "custom_clock_unqualified",
            [record.get("reason") for record in self.records],
        )
        del self.runtime.clock

        calls = []

        def foreground(native, **kwargs):
            calls.append(threading.get_ident())
            yield [], {"action": {"type": "end_turn"}}

        # Both known unsupported profiles must retain the synchronous caller.
        self.runtime.expiration_runtime_factory = object()
        list(execute(self.runtime, self.context(), foreground))
        self.runtime.expiration_runtime_factory = OwnedExpirationFactory(
            characters={10: {"id": 10, "account_id": 1, "map_id": 1134}},
            monsters={},
            decks={10: b"deck"},
            actor_id=10,
        )
        self.fight.rift_wave_state = {"wave": 1}
        list(execute(self.runtime, self.context(), foreground))
        del self.fight.rift_wave_state

        with patch.dict("sys.modules", {"wakfu_server.combat_background_work": None}):
            self.assertEqual(admission(self.shared), "server_capability_missing")
            list(execute(self.runtime, self.context(), foreground))
        self.assertEqual(calls, [threading.get_ident()] * 3)

    def _slow_empty_runner(self, native):
        time.sleep(0.015)
        if False:
            yield [], {}

    def _wait_for_background(self):
        from wakfu_server.combat_background_work import NATIVE_WORK

        key = ("native-ai", id(self.shared))
        self._wait_until(lambda: NATIVE_WORK.status(key) is None)

    @staticmethod
    def _wait_until(predicate):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.005)
        if not predicate():
            raise AssertionError("background operation did not finish")


if __name__ == "__main__":
    unittest.main()
