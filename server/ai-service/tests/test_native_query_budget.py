"""Search expiry preserves owner time, source guards and certified incumbents."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from test_native_session import make_runtime, StubOracle, StubTransport
from test_query_search import FakeNativeSession, run_search
from wakfu_ai.bridge.world_bridge import NativeSession
from wakfu_ai.native.native_deadline import (
    bounded,
    check,
    remaining,
    query_budget,
    NativeSearchAllowanceExceeded,
)
from wakfu_ai.planning.query_sessions import QuerySessions


class NativeQueryBudgetTests(unittest.TestCase):
    def test_cooperative_query_stops_before_consuming_commit_reserve(self):
        now = [0.0]
        with bounded(1.2, clock=lambda: now[0]):
            now[0] = 0.6
            with self.assertRaises(NativeSearchAllowanceExceeded):
                with query_budget(reserve_ms=500):
                    while True:
                        now[0] = min(0.7, now[0] + 0.01)
                        check()
            self.assertAlmostEqual(remaining(), 0.5)
        self.assertIsNone(remaining())

    def test_opaque_late_result_is_rejected_without_claiming_time_is_recovered(self):
        now = [0.0]
        with bounded(1.2, clock=lambda: now[0]):
            now[0] = 0.6
            with self.assertRaises(NativeSearchAllowanceExceeded):
                with query_budget(reserve_ms=500):
                    now[0] += 0.55
            self.assertAlmostEqual(remaining(), 0.05)

    def test_real_owner_expiry_remains_fatal(self):
        now = [0.0]
        with bounded(1.2, clock=lambda: now[0]):
            with self.assertRaises(TimeoutError) as raised:
                with query_budget(reserve_ms=500):
                    now[0] = 1.3
                    check()
            self.assertNotIsInstance(raised.exception, NativeSearchAllowanceExceeded)

    def test_short_remote_allowance_cannot_extend_local_owner_reserve(self):
        now = [0.0]
        with bounded(1.2, clock=lambda: now[0]):
            with query_budget(allowance_ms=1000000, reserve_ms=500):
                self.assertAlmostEqual(remaining(), 0.7)
            with query_budget(allowance_ms=40, reserve_ms=500):
                self.assertAlmostEqual(remaining(), 0.04)
            self.assertAlmostEqual(remaining(), 1.2)

    def test_invalid_allowances_and_exhausted_reserve_do_not_run_query(self):
        now = [0.0]
        for allowance in (True, -1, float("nan"), float("inf"), "40"):
            with self.subTest(allowance=allowance), self.assertRaises(ValueError):
                with query_budget(allowance_ms=allowance):
                    self.fail("invalid allowance authorized work")
        with bounded(0.5, clock=lambda: now[0]):
            with self.assertRaises(NativeSearchAllowanceExceeded):
                with query_budget(reserve_ms=500):
                    self.fail("commit reserve authorized work")

    def test_unrelated_operation_timeout_is_not_reclassified_as_budget_expiry(self):
        now = [0.0]
        original = TimeoutError("database operation timed out")
        with bounded(2.0, clock=lambda: now[0]):
            with self.assertRaises(TimeoutError) as raised:
                with query_budget(reserve_ms=500):
                    raise original
        self.assertIs(raised.exception, original)

    def test_native_session_reports_search_expiry_without_adopting_private_result(self):
        value = make_runtime()
        session = NativeSession(
            StubOracle(value),
            StubTransport(),
            object(),
            policy={},
            policy_version="test",
            fight_instance_id="test",
        )
        before = deepcopy(vars(value.fight.current))
        now = [0.0]
        calls = []

        def costly(operation, key, request):
            calls.append(True)
            now[0] = 0.11
            check()
            self.fail("late query result was accepted")

        with patch.object(session, "_query", costly):
            with bounded(1.0, clock=lambda: now[0]):
                reply = session.query(
                    dict(
                        id="1",
                        operation="preview",
                        state=session.root,
                        searchAllowanceMs=100,
                        action=dict(type="move", path=[[1, 0, 0]]),
                    )
                )
                self.assertAlmostEqual(remaining(), 0.89)
        self.assertEqual(calls, [True])
        self.assertFalse(reply["supported"])
        self.assertEqual(
            reply["unknownDependencies"], ["native_search_allowance_exhausted"]
        )
        self.assertAlmostEqual(reply["nativeBudgetMs"], 890)
        self.assertEqual(vars(value.fight.current), before)

    def test_source_change_during_expired_query_remains_a_fatal_guard_failure(self):
        value = make_runtime()
        session = NativeSession(
            StubOracle(value),
            StubTransport(),
            object(),
            policy={},
            policy_version="test",
            fight_instance_id="test",
        )
        now = [0.0]

        def corrupted(operation, key, request):
            value.fight.current.hp -= 1
            now[0] = 0.11
            check()

        with patch.object(session, "_query", corrupted):
            with bounded(1.0, clock=lambda: now[0]):
                with self.assertRaisesRegex(ValueError, "source changed"):
                    session.query(
                        dict(
                            id="1",
                            operation="preview",
                            state=session.root,
                            searchAllowanceMs=100,
                            action=dict(type="move", path=[[1, 0, 0]]),
                        )
                    )

    def test_real_search_retains_certified_move_when_next_query_uses_its_allowance(
        self,
    ):
        fake = FakeNativeSession(
            spells=[dict(spellId=10, level=1)],
            cells=[(0, 0, 0), (1, 0, 0), (3, 0, 0), (0, 0, 1)],
            edges=[((0, 0, 0), (1, 0, 0))],
            effects={10: "damage"},
        )
        fake.envelope.update(
            nativeBudgetMs=1200,
            warmStart=dict(
                schema="verified-turn-continuation-v1",
                actions=[dict(type="move", path=[[1, 0, 0]])],
            ),
        )
        fake.envelope["policy"].update(searchTimeFraction=1)
        fake.envelope["policy"]["limits"].update(depth=1, nodes=8)
        bridge = NativeSession.__new__(NativeSession)
        bridge.states, bridge.policy = fake.states, fake.envelope["policy"]
        bridge.guard = check
        now, attempts = [0.0], []
        original = fake.request

        def native_query(operation, key, query):
            attempts.append((operation, now[0]))
            duration = (
                0.6
                if operation == "repertoire"
                else (0.01 if query.get("action", {}).get("type") == "move" else 0.55)
            )
            finish = now[0] + duration
            while now[0] < finish:
                # Simulate cooperative native work, not invented game rules.
                now[0] = min(finish, now[0] + 0.01)
                check()
            return original(query)["result"]

        bridge._query = native_query
        fake.request = bridge.query
        with bounded(1.2, clock=lambda: now[0]):
            decision = run_search(fake, clock=lambda: now[0])
            self.assertGreaterEqual(remaining(), 0.4999)
        self.assertEqual(decision["action"], dict(type="move", path=[[1, 0, 0]]))
        self.assertTrue(decision["searchBudgetEvidence"]["rootActionCertified"])
        self.assertIn(
            "native_search_allowance_exhausted", decision["unknownDependencies"]
        )
        self.assertLessEqual(now[0], 0.7001)
        self.assertEqual(
            [operation for operation, _ in attempts],
            ["preview", "repertoire", "preview"],
        )


class ServiceQueryAllowanceTests(unittest.TestCase):
    def test_service_preserves_smaller_risk_hint_and_forwards_explicit_incumbent_reset(
        self,
    ):
        from test_query_sessions import FakeStore

        store = FakeStore()
        service = QuerySessions(clock=lambda: 0.0)
        payload = dict(
            protocol=3,
            requestId="risk-allowance",
            sourceKey="c" * 64,
            catalogManifest=store.catalog,
            rootState=store.root,
            actor_id=1,
            root=dict(
                key=store.root,
                nativeContext=store.root,
                currentId=1,
                phase="active",
                actors=[],
            ),
            policy={},
            nativeBudgetMs=20000,
        )

        def planner(envelope, store, **kwargs):
            yield dict(
                id="risk:1",
                operation="project_turn",
                state=store.root,
                searchAllowanceMs=500,
                incumbent=None,
            )

        with patch("wakfu_ai.planning.query_sessions.search", planner):
            first = service.decide(payload, store)
        self.assertEqual(first["queries"][0]["searchAllowanceMs"], 500)
        self.assertIn("incumbent", first)
        self.assertIsNone(first["incumbent"])
        self.assertNotIn("incumbent", first["queries"][0])

    def test_service_cannot_inflate_an_explicit_hint_beyond_the_owner_reserve(self):
        from test_query_sessions import FakeStore

        store = FakeStore()
        service = QuerySessions(clock=lambda: 0.0)
        payload = dict(
            protocol=3,
            requestId="oversize-allowance",
            sourceKey="c" * 64,
            catalogManifest=store.catalog,
            rootState=store.root,
            actor_id=1,
            root=dict(
                key=store.root,
                nativeContext=store.root,
                currentId=1,
                phase="active",
                actors=[],
            ),
            policy={},
            nativeBudgetMs=1200,
        )

        def planner(envelope, store, **kwargs):
            yield dict(
                id="1",
                operation="preview",
                state=store.root,
                searchAllowanceMs=100000,
                action=dict(type="move", path=[[1, 0, 0]]),
            )

        with patch("wakfu_ai.planning.query_sessions.search", planner):
            first = service.decide(payload, store)
        self.assertEqual(first["queries"][0]["searchAllowanceMs"], 700)

    def test_source_bound_reply_freezes_allowance_across_retries(self):
        from test_query_sessions import FakeStore

        store = FakeStore()
        now = [0.0]
        service = QuerySessions(clock=lambda: now[0])
        payload = dict(
            protocol=3,
            requestId="allowance",
            sourceKey="c" * 64,
            catalogManifest=store.catalog,
            rootState=store.root,
            actor_id=1,
            root=dict(
                key=store.root,
                nativeContext=store.root,
                currentId=1,
                phase="active",
                actors=[],
            ),
            policy={},
            nativeBudgetMs=1200,
        )

        def planner(envelope, store, **kwargs):
            answer = yield dict(
                id="1",
                operation="preview",
                state=store.root,
                action=dict(type="move", path=[[1, 0, 0]]),
            )
            self.assertFalse(answer["supported"])
            return dict(
                protocol=3,
                requestId=envelope["requestId"],
                sourceKey=envelope["sourceKey"],
                rootState=envelope["rootState"],
                action=dict(type="end_turn"),
            )

        with patch("wakfu_ai.planning.query_sessions.search", planner):
            first = service.decide(payload, store)
            self.assertEqual(first["queries"][0]["searchAllowanceMs"], 700)
            now[0] = 0.2
            self.assertEqual(service.decide(deepcopy(payload), store), first)
            completed = service.decide(
                dict(
                    requestId="allowance",
                    sourceKey="c" * 64,
                    response=dict(
                        id="1",
                        supported=False,
                        unknownDependencies=["native_search_allowance_exhausted"],
                    ),
                ),
                store,
            )
            self.assertEqual(completed["status"], "decided")


if __name__ == "__main__":
    unittest.main()
