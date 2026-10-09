import unittest
from unittest.mock import patch
from wakfu_ai.context.native_context import encode
from wakfu_ai.native.native_deadline import remaining
from wakfu_ai.planning.query_sessions import QuerySessions


class QueryInitializationDeadlineTests(unittest.TestCase):
    def test_complete_verification_consumes_owner_budget_before_first_query(self):
        self._run_case(10, expires=True)

    def test_search_receives_only_budget_remaining_after_verification(self):
        self._run_case(50, expires=False)

    def test_abandoned_owner_deadline_releases_capacity_without_waiting_for_ttl(self):
        now = [10.0]
        graph = encode({"future": "complete"})
        closed = []

        class Store:
            def seal_manifest(self, digest):
                return {"complete": True}

            def json(self, digest):
                return graph

        def search(payload, store, **kwargs):
            try:
                yield {"id": "query-1", "operation": "state"}
            finally:
                closed.append(payload["requestId"])

        payload = dict(
            protocol=3,
            requestId="abandoned",
            sourceKey="c" * 64,
            catalogManifest="b" * 64,
            rootState="a" * 64,
            actor_id=-7,
            policy={},
            nativeBudgetMs=10,
            root=dict(
                key="a" * 64,
                nativeContext="a" * 64,
                currentId=-7,
                phase="active",
                actors=[],
            ),
        )
        sessions = QuerySessions(capacity=1, ttl=300, clock=lambda: now[0])
        with patch("wakfu_ai.planning.query_sessions.search", search):
            sessions.decide(payload, Store())
            now[0] += 0.02
            replacement = dict(payload, requestId="replacement")
            reply = sessions.decide(replacement, Store())
            self.assertEqual(reply["status"], "query")
            self.assertEqual(closed, ["abandoned"])
            self.assertNotIn("abandoned", sessions.sessions)
            sessions.cancel(dict(requestId="replacement", sourceKey="c" * 64))

    def _run_case(self, budget, *, expires):
        now = [10.0]
        graph = encode({"future": b"complete-data"})

        class Store:
            def seal_manifest(self, digest):
                now[0] += 0.008
                return {"complete": True}

            def json(self, digest):
                now[0] += 0.004
                return graph

        seen = []

        def search(payload, store, **kwargs):
            seen.append(payload["nativeBudgetMs"])
            yield {"id": "query-1", "operation": "state"}

        payload = dict(
            protocol=3,
            requestId="one",
            sourceKey="c" * 64,
            catalogManifest="b" * 64,
            rootState="a" * 64,
            actor_id=-7,
            policy={},
            nativeBudgetMs=budget,
            root=dict(
                key="a" * 64,
                nativeContext="a" * 64,
                currentId=-7,
                phase="active",
                actors=[],
            ),
        )
        sessions = QuerySessions(clock=lambda: now[0])
        with patch("wakfu_ai.planning.query_sessions.search", search):
            if expires:
                with self.assertRaises(TimeoutError):
                    sessions.decide(payload, Store())
                self.assertEqual(seen, [])
                self.assertEqual(sessions.sessions, {})
            else:
                reply = sessions.decide(payload, Store())
                self.assertEqual(reply["status"], "query")
                self.assertEqual(
                    set(reply["backendPreparation"]),
                    {"catalogSeal", "rootGraph", "firstQuery"},
                )
                for phase in reply["backendPreparation"].values():
                    self.assertEqual(set(phase), {"wallMs", "threadCpuMs"})
                    self.assertTrue(all(value >= 0 for value in phase.values()))
                self.assertAlmostEqual(seen[0], 38)
                self.assertEqual(sessions.sessions["one"]["initial"], payload)
                sessions.cancel(dict(requestId="one", sourceKey="c" * 64))
        self.assertIsNone(remaining())
