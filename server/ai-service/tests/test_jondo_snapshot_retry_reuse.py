"""Reuse only unchanged advisory preparation; every chosen action stays native."""
from copy import deepcopy
from contextlib import contextmanager
import time
import unittest
from unittest.mock import patch

from test_jondo_bridge import Oracle, Runtime, Transport, reply
from wakfu_ai.bridge import jondo_entry
from wakfu_ai.native.native_deadline import bounded as native_bounded


class SnapshotRetryReuseTests(unittest.TestCase):
    def snapshot(self, oracle, *, excluded_actions, budget_ms):
        result = dict(
            protocol=1,
            requestId="prepared-request",
            source=dict(nativeIdentity=oracle.state_identity(oracle.runtime)),
            board=dict(cells=[dict(id=0, xyz=[0, 0, 0])]),
            native=dict(usage=[dict(spellId=7, count=0)]),
            limits=dict(budgetMs=budget_ms, maxActions=1),
            excludedActions=list(excluded_actions),
        )
        self.prepared.append((result, deepcopy(result)))
        return result

    def setUp(self):
        self.prepared = []

    def drive(self, oracle, choose, *, max_actions=1):
        transport = Transport(choose)
        with patch.object(jondo_entry, "build_snapshot", self.snapshot):
            deliveries = list(
                jondo_entry.run_prepared_turn(
                    oracle.runtime,
                    oracle,
                    object(),
                    transport,
                    deadline=time.monotonic() + 5,
                    max_actions=max_actions,
                )
            )
        return deliveries, transport

    def test_retries_share_one_preparation_with_fresh_custody_and_feedback(self):
        class RejectTwo(Oracle):
            def commit(self, action, *, stats_serializer):
                if action.get("spellId") in (98, 99):
                    self.calls.append(deepcopy(action))
                    raise ValueError("Native action rejected")
                return super().commit(action, stats_serializer=stats_serializer)

        oracle = RejectTwo(Runtime())

        def choose(request, count):
            return reply(
                request,
                dict(
                    type="cast",
                    spellId=(99, 98, 7)[count - 1],
                    level=1,
                    target=[1, 0, 0],
                ),
            )

        deliveries, transport = self.drive(oracle, choose)
        self.assertEqual(len(self.prepared), 1)
        requests = transport.requests
        self.assertEqual(len(requests), 3)
        self.assertEqual(len({row["requestId"] for row in requests}), 3)
        self.assertTrue(all(row["requestId"] != "prepared-request" for row in requests))
        self.assertEqual([len(row["excludedActions"]) for row in requests], [0, 1, 2])
        self.assertTrue(all(row["source"] == requests[0]["source"] for row in requests))
        self.assertTrue(all(row["board"] == requests[0]["board"] for row in requests))
        self.assertTrue(all(row["native"]["turnActions"] == [] for row in requests))
        self.assertTrue(all(row["limits"]["maxActions"] == 1 for row in requests))
        self.assertEqual(deliveries[0][1]["action"]["spellId"], 7)
        self.assertEqual(len(deliveries[0][1]["rejectedActions"]), 2)
        self.assertEqual(self.prepared[0][0], self.prepared[0][1])

    def test_successful_commit_rebuilds_facts_and_records_only_committed_history(self):
        oracle = Oracle(Runtime())
        deliveries, transport = self.drive(
            oracle,
            lambda request, count: reply(
                request, dict(type="cast", spellId=count + 6, level=1, target=[1, 0, 0])
            ),
            max_actions=2,
        )
        self.assertEqual(len(self.prepared), 2)
        self.assertNotEqual(
            transport.requests[0]["source"], transport.requests[1]["source"]
        )
        self.assertEqual(transport.requests[0]["native"]["turnActions"], [])
        self.assertEqual(
            transport.requests[1]["native"]["turnActions"],
            [dict(type="cast", spellId=7, target=[1, 0, 0])],
        )
        self.assertEqual(
            [row[1]["action"]["spellId"] for row in deliveries[:2]], [7, 8]
        )
        self.assertTrue(all(value == original for value, original in self.prepared))

    def test_changed_source_before_retry_rebuilds_and_discards_old_rejections(self):
        class ChangedAfterRejection(Oracle):
            def __init__(self, runtime):
                super().__init__(runtime)
                self.reads_after_failure = 0
                self.failed = False

            def commit(self, action, *, stats_serializer):
                try:
                    return super().commit(action, stats_serializer=stats_serializer)
                finally:
                    self.failed = True

            def state_identity(self, runtime):
                if self.failed:
                    self.reads_after_failure += 1
                    if self.reads_after_failure > 1:
                        self.identity = "concurrent-native-transition"
                return self.identity

        oracle = ChangedAfterRejection(Runtime())
        transport = Transport(
            lambda request, count: reply(
                request,
                dict(
                    type="cast",
                    spellId=99 if count == 1 else 7,
                    level=1,
                    target=[1, 0, 0],
                ),
            )
        )
        with patch.object(jondo_entry, "build_snapshot", self.snapshot):
            deliveries = list(
                jondo_entry.run_prepared_turn(
                    oracle.runtime,
                    oracle,
                    object(),
                    transport,
                    deadline=time.monotonic() + 5,
                    max_actions=1,
                )
            )
        self.assertEqual(len(self.prepared), 2)
        self.assertEqual(len(transport.requests), 2)
        self.assertNotEqual(
            transport.requests[0]["source"], transport.requests[1]["source"]
        )
        self.assertEqual(transport.requests[1]["excludedActions"], [])
        self.assertEqual(deliveries[0][1]["rejectedActions"], [])
        self.assertEqual([row["spellId"] for row in oracle.calls], [99, 7])

    def test_changed_source_during_reused_rpc_never_commits_its_reply(self):
        oracle = Oracle(Runtime())

        def choose(request, count):
            if count == 2:
                oracle.identity = "concurrent-native-transition"
            return reply(
                request,
                dict(
                    type="cast",
                    spellId=99 if count == 1 else 7,
                    level=1,
                    target=[1, 0, 0],
                ),
            )

        transport = Transport(choose)
        with patch.object(jondo_entry, "build_snapshot", self.snapshot):
            with self.assertRaisesRegex(
                ValueError, "source changed during Jondo decision"
            ):
                list(
                    jondo_entry.run_prepared_turn(
                        oracle.runtime,
                        oracle,
                        object(),
                        transport,
                        deadline=time.monotonic() + 5,
                        max_actions=1,
                    )
                )
        self.assertEqual(len(self.prepared), 1)
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual([row["spellId"] for row in oracle.calls], [99])

    def test_changed_turn_or_presentation_before_retry_stops_the_driver(self):
        for change in ("actor", "turn", "ack", "fifo"):
            with self.subTest(change=change):
                self.prepared = []

                class TransitionAfterRejection(Oracle):
                    def commit(self, action, *, stats_serializer):
                        try:
                            return super().commit(
                                action, stats_serializer=stats_serializer
                            )
                        finally:
                            if change == "actor":
                                self.runtime.fight.current.id = -9
                            elif change == "turn":
                                self.runtime.fight.turn_id = 2
                            elif change == "ack":
                                self.runtime.awaiting_ack = 1
                            else:
                                self.runtime.pending = ["fifo"]

                oracle = TransitionAfterRejection(Runtime())
                deliveries, transport = self.drive(
                    oracle,
                    lambda request, count: reply(
                        request,
                        dict(type="cast", spellId=99, level=1, target=[1, 0, 0]),
                    ),
                )
                self.assertEqual(deliveries, [])
                self.assertEqual(len(self.prepared), 1)
                self.assertEqual(len(transport.requests), 1)
                self.assertEqual(oracle.runtime.ends, 0)

    def test_only_end_turn_passes_verified_current_observations_to_native_facing(self):
        class FacingOracle(Oracle):
            def __init__(self, runtime):
                super().__init__(runtime)
                self.commit_kwargs = []

            def commit(self, action, **kwargs):
                self.commit_kwargs.append(dict(kwargs))
                return super().commit(
                    action, stats_serializer=kwargs["stats_serializer"]
                )

        ordinary_snapshot = self.snapshot

        def observed_snapshot(oracle, **kwargs):
            request = ordinary_snapshot(oracle, **kwargs)
            request["source"].update(actorId=-7, turnId=1, stateRevision=7)
            request["board"] = dict(
                cells=[dict(id=0, xyz=[0, 0, 0]), dict(id=1, xyz=[1, 0, 0])],
                actors=[
                    dict(id=-7, cell=0, hidden=False),
                    dict(id=7, cell=1, hidden=False),
                ],
            )
            return request

        for action in (
            dict(type="cast", spellId=7, level=1, target=[1, 0, 0]),
            dict(type="end_turn"),
        ):
            with self.subTest(action=action["type"]):
                oracle = FacingOracle(Runtime())
                transport = Transport(lambda request, count: reply(request, action))
                with patch.object(jondo_entry, "build_snapshot", observed_snapshot):
                    list(
                        jondo_entry.run_prepared_turn(
                            oracle.runtime,
                            oracle,
                            object(),
                            transport,
                            deadline=time.monotonic() + 5,
                            max_actions=1,
                        )
                    )
                if action["type"] == "cast":
                    self.assertNotIn("defensive_facing", oracle.commit_kwargs[0])
                else:
                    self.assertEqual(
                        oracle.commit_kwargs[0]["defensive_facing"],
                        dict(
                            actorId=-7,
                            turnId=1,
                            stateRevision=7,
                            visibleActorIds=[-7, 7],
                            actors=[
                                dict(id=-7, position=[0, 0, 0]),
                                dict(id=7, position=[1, 0, 0]),
                            ],
                            rivals=[],
                        ),
                    )

    def test_retry_refreshes_remaining_budget_and_honors_original_deadline(self):
        now = [100.0]

        @contextmanager
        def controlled_deadline(deadline):
            with native_bounded(deadline, clock=lambda: now[0]):
                yield

        oracle = Oracle(Runtime())

        def choose(request, count):
            if count == 1:
                now[0] += 0.2
            else:
                now[0] = 101.0
            return reply(
                request, dict(type="cast", spellId=99, level=1, target=[1, 0, 0])
            )

        transport = Transport(choose)
        with patch.object(jondo_entry, "build_snapshot", self.snapshot), patch.object(
            jondo_entry, "bounded", controlled_deadline
        ), patch.object(jondo_entry.time, "monotonic", side_effect=lambda: now[0]):
            with self.assertRaises(TimeoutError):
                list(
                    jondo_entry.run_prepared_turn(
                        oracle.runtime,
                        oracle,
                        object(),
                        transport,
                        deadline=101.0,
                        max_actions=1,
                    )
                )
        self.assertEqual(len(self.prepared), 1)
        self.assertEqual(len(transport.requests), 2)
        self.assertLess(
            transport.requests[1]["limits"]["budgetMs"],
            transport.requests[0]["limits"]["budgetMs"],
        )
        self.assertEqual(len(oracle.calls), 1)

    def test_presentation_barriers_stop_reuse_after_committed_action(self):
        for barrier in ("awaiting_ack", "pending"):
            with self.subTest(barrier=barrier):
                self.prepared = []
                oracle = Oracle(Runtime())
                transport = Transport(
                    lambda request, count: reply(
                        request,
                        dict(
                            type="cast",
                            spellId=99 if count == 1 else 7,
                            level=1,
                            target=[1, 0, 0],
                        ),
                    )
                )
                with patch.object(jondo_entry, "build_snapshot", self.snapshot):
                    driver = jondo_entry.run_prepared_turn(
                        oracle.runtime,
                        oracle,
                        object(),
                        transport,
                        deadline=time.monotonic() + 5,
                        max_actions=2,
                    )
                    self.assertEqual(next(driver)[1]["action"]["spellId"], 7)
                    setattr(
                        oracle.runtime,
                        barrier,
                        1 if barrier == "awaiting_ack" else ["fifo"],
                    )
                    self.assertEqual(list(driver), [])
                self.assertEqual(len(self.prepared), 1)
                self.assertEqual(len(transport.requests), 2)
                self.assertEqual(oracle.runtime.ends, 0)

    def test_service_timing_forwards_only_finite_known_fields_with_the_expected_scope(
        self,
    ):
        valid = dict(
            parseMs=2,
            queueWaitMs=3.5,
            planningMs=4,
            totalMs=9.5,
            scope="received_frame_to_completed_decision",
        )
        oracle = Oracle(Runtime())

        def choose(request, count):
            result = reply(
                request, dict(type="cast", spellId=7, level=1, target=[1, 0, 0])
            )
            result["serviceTiming"] = dict(
                valid, unexpected=dict(raw="never log this payload")
            )
            return result

        deliveries, _ = self.drive(oracle, choose)
        self.assertEqual(deliveries[0][1]["jondoServiceTiming"], valid)
        for field, value in (
            ("parseMs", float("nan")),
            ("queueWaitMs", -1),
            ("planningMs", True),
            ("totalMs", 10**4000),
            ("scope", "unverified"),
            ("parseMs", {"nested": "payload"}),
        ):
            with self.subTest(field=field, value_type=type(value).__name__):
                self.assertIsNone(
                    jondo_entry._service_timing(
                        dict(serviceTiming=dict(valid, **{field: value}))
                    )
                )


if __name__ == "__main__":
    unittest.main()
