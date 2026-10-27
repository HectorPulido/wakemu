"""Transient capacity errors share the existing source and turn allowance."""
from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch

from test_jondo_bridge import Oracle, Runtime, reply, request_fixture
from wakfu_ai.bridge import jondo_entry
from wakfu_ai.native.native_deadline import bounded as native_bounded


class BusyTransport:
    def __init__(self, choose):
        self.choose, self.requests = choose, []

    def request(self, endpoint, request, *, deadline):
        self.requests.append(deepcopy(request))
        return self.choose(request, len(self.requests))


class JondoBusyRetryTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.delays = []
        self.builds = 0
        self.oracle = Oracle(Runtime())

    def snapshot(self, *args, **kwargs):
        self.builds += 1
        return request_fixture(*args, **kwargs)

    @contextmanager
    def deadline(self, deadline):
        with native_bounded(deadline, clock=lambda: self.now):
            yield

    def sleep(self, delay):
        self.delays.append(delay)
        self.now += delay

    @contextmanager
    def environment(self, *, sleep=None):
        with patch.object(jondo_entry, "build_snapshot", self.snapshot), patch.object(
            jondo_entry, "bounded", self.deadline
        ), patch.object(
            jondo_entry.time, "monotonic", side_effect=lambda: self.now
        ), patch.object(
            jondo_entry.time, "sleep", side_effect=sleep or self.sleep
        ):
            yield

    def driver(self, transport):
        return jondo_entry.run_prepared_turn(
            self.oracle.runtime,
            self.oracle,
            object(),
            transport,
            deadline=101.0,
            max_actions=1,
        )

    def test_capacity_error_then_valid_reply_reuses_snapshot_without_passing_the_action(
        self,
    ):
        def choose(request, count):
            if count == 1:
                return 503, dict(error="Jondo capacity reached")
            return 200, reply(
                request, dict(type="cast", spellId=7, level=1, target=[1, 0, 0])
            )

        transport = BusyTransport(choose)
        with self.environment():
            deliveries = list(self.driver(transport))
        self.assertEqual(self.builds, 1)
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(len({row["requestId"] for row in transport.requests}), 2)
        self.assertEqual(
            transport.requests[0]["source"], transport.requests[1]["source"]
        )
        self.assertLess(
            transport.requests[1]["limits"]["budgetMs"],
            transport.requests[0]["limits"]["budgetMs"],
        )
        self.assertEqual([row["spellId"] for row in self.oracle.calls], [7])
        self.assertEqual(deliveries[0][1]["action"]["type"], "cast")
        self.assertEqual(self.delays, [0.025])

    def test_capacity_reply_with_changed_source_is_not_retried_or_committed(self):
        def choose(request, count):
            self.oracle.identity = "changed-during-capacity-reply"
            return 503, dict(error="busy")

        transport = BusyTransport(choose)
        with self.environment(), self.assertRaisesRegex(ValueError, "source changed"):
            list(self.driver(transport))
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(self.oracle.calls, [])
        self.assertEqual(self.delays, [])

    def test_source_change_during_short_backoff_aborts_before_another_rpc(self):
        def changed_sleep(delay):
            self.sleep(delay)
            self.oracle.identity = "changed-during-short-backoff"

        transport = BusyTransport(lambda request, count: (503, dict(error="busy")))
        with self.environment(sleep=changed_sleep), self.assertRaisesRegex(
            ValueError, "capacity retry"
        ):
            list(self.driver(transport))
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(self.builds, 1)
        self.assertEqual(self.oracle.calls, [])

    def test_invalid_request_errors_are_not_retried(self):
        transport = BusyTransport(
            lambda request, count: (400, dict(error="Invalid source"))
        )
        with self.environment(), self.assertRaisesRegex(
            ValueError, "rejected compact snapshot"
        ):
            list(self.driver(transport))
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(self.oracle.calls, [])
        self.assertEqual(self.delays, [])

    def test_capacity_backoff_cannot_renew_the_original_turn_deadline(self):
        def choose(request, count):
            self.now = 100.99
            return 503, dict(error="busy")

        transport = BusyTransport(choose)
        with self.environment(), self.assertRaises(TimeoutError):
            list(self.driver(transport))
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(self.oracle.calls, [])
        self.assertLessEqual(self.delays[0], 0.025)
        self.assertAlmostEqual(self.now, 101.0)

    def test_permanent_capacity_error_uses_only_the_existing_three_attempts(self):
        transport = BusyTransport(lambda request, count: (503, dict(error="busy")))
        with self.environment(), self.assertRaisesRegex(
            ValueError, "rejected compact snapshot"
        ):
            list(self.driver(transport))
        self.assertEqual(self.builds, 1)
        self.assertEqual(len(transport.requests), 3)
        self.assertEqual(self.oracle.calls, [])
        self.assertEqual(self.delays, [0.025, 0.025])

    def test_changed_owner_or_presentation_stops_capacity_retry(self):
        for change in ("actor", "turn", "ack", "fifo"):
            with self.subTest(change=change):
                self.setUp()

                def choose(request, count):
                    if change == "actor":
                        self.oracle.runtime.fight.current.id = -9
                    elif change == "turn":
                        self.oracle.runtime.fight.turn_id = 2
                    elif change == "ack":
                        self.oracle.runtime.awaiting_ack = 1
                    else:
                        self.oracle.runtime.pending = ["fifo"]
                    return 503, dict(error="busy")

                transport = BusyTransport(choose)
                with self.environment():
                    self.assertEqual(list(self.driver(transport)), [])
                self.assertEqual(len(transport.requests), 1)
                self.assertEqual(self.oracle.calls, [])
                self.assertEqual(self.delays, [])

    def test_decision_metrics_include_busy_rpcs_and_rejected_native_commit_cost(self):
        for failure in ("capacity", "native_rejection"):
            with self.subTest(failure=failure):
                self.setUp()
                clock = self

                class TimedOracle(Oracle):
                    def commit(self, action, **kwargs):
                        clock.now += 0.006 if action.get("spellId") == 99 else 0.004
                        return super().commit(action, **kwargs)

                self.oracle = TimedOracle(Runtime())
                original_snapshot = JondoBusyRetryTests.snapshot.__get__(self)

                def timed_snapshot(*args, **kwargs):
                    self.now += 0.005
                    return original_snapshot(*args, **kwargs)

                self.snapshot = timed_snapshot

                def choose(request, count):
                    self.now += 0.01 * count
                    good = dict(type="cast", spellId=7, level=1, target=[1, 0, 0])
                    if failure == "capacity" and count == 1:
                        return 503, dict(error="busy")
                    if failure == "native_rejection":
                        return 200, reply(
                            request,
                            dict(type="cast", spellId=99, level=1, target=[1, 0, 0]),
                            [good],
                        )
                    return 200, reply(request, good)

                transport = BusyTransport(choose)
                with self.environment():
                    diagnostic = list(self.driver(transport))[0][1]
                total = diagnostic["decisionPhaseElapsedMs"]
                self.assertAlmostEqual(total["snapshot"], 5.0)
                if failure == "capacity":
                    self.assertEqual(diagnostic["decisionAttempts"], 2)
                    self.assertEqual(diagnostic["busyRetries"], 1)
                    self.assertAlmostEqual(total["plannerRpc"], 30.0)
                    self.assertAlmostEqual(
                        diagnostic["phaseElapsedMs"]["plannerRpc"], 20.0
                    )
                    self.assertAlmostEqual(diagnostic["decisionElapsedMs"], 64.0)
                else:
                    self.assertEqual(diagnostic["decisionAttempts"], 1)
                    self.assertEqual(diagnostic["busyRetries"], 0)
                    self.assertAlmostEqual(total["nativeCommit"], 10.0)
                    self.assertAlmostEqual(
                        diagnostic["phaseElapsedMs"]["nativeCommit"], 4.0
                    )
                    self.assertAlmostEqual(diagnostic["decisionElapsedMs"], 25.0)


if __name__ == "__main__":
    unittest.main()
