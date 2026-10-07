"""The concurrency diagnostic must validate both actual v3 response shapes."""
import unittest
from unittest.mock import patch

from benchmarks.benchmark_native_concurrent import MeasuredTransport
from wakfu_ai.bridge.world_bridge import ContextTransport


class ConcurrentBenchmarkIdentityTests(unittest.TestCase):
    def setUp(self):
        self.transport = MeasuredTransport("http://unused.invalid", "encounter")
        self.transport.turn_started = 0
        self.payload = dict(
            protocol=3,
            fightInstanceId="encounter",
            requestId="request",
            sourceKey="a" * 64,
        )

    def test_native_query_and_final_decision_shapes_have_source_bound_identity(self):
        query = dict(
            status="query", requestId="request", sourceKey="a" * 64, queries=[{}]
        )
        final = dict(
            status="decided",
            decision=dict(
                requestId="request", sourceKey="a" * 64, action=dict(type="end_turn")
            ),
        )
        with patch.object(ContextTransport, "request", side_effect=[query, final]):
            self.assertEqual(self.transport.request("/v3/decide", self.payload), query)
            self.assertEqual(
                self.transport.request(
                    "/v3/decide",
                    dict(requestId="request", sourceKey="a" * 64, response={}),
                ),
                final,
            )
        self.assertEqual(self.transport.decisions, [final["decision"]])
        self.assertEqual(self.transport.http["/v3/decide"]["failures"], [])

    def test_foreign_identity_fails_for_queries_and_completed_decisions(self):
        for status in ("query", "decided"):
            for field, bad in (
                ("requestId", "foreign-request"),
                ("sourceKey", "b" * 64),
            ):
                with self.subTest(status=status, field=field):
                    identity = dict(requestId="request", sourceKey="a" * 64)
                    identity[field] = bad
                    reply = (
                        dict(status=status, **identity)
                        if status == "query"
                        else dict(status=status, decision=identity)
                    )
                    with patch.object(ContextTransport, "request", return_value=reply):
                        with self.assertRaisesRegex(
                            AssertionError, "Foreign native search response"
                        ):
                            self.transport.request("/v3/decide", self.payload)

    def test_foreign_encounter_is_rejected_before_http(self):
        with patch.object(ContextTransport, "request") as request:
            with self.assertRaisesRegex(AssertionError, "Foreign native encounter"):
                self.transport.request(
                    "/v3/decide", dict(self.payload, fightInstanceId="foreign")
                )
            request.assert_not_called()


class ConcurrentBenchmarkFixtureTests(unittest.TestCase):
    def test_distinct_encounter_hp_has_a_valid_native_characteristic_snapshot(self):
        from benchmarks.benchmark_native_concurrent import encounter
        from wakfu_server.combat_snapshot_wire import snapshot_characteristics

        for index in (0, 1, 4, 5):
            with self.subTest(index=index):
                case = encounter("http://unused.invalid", index)
                actor = case["runtime"].fight.actors[7]
                self.assertEqual(actor.hp, 60 - index % 5)
                self.assertEqual(actor.max_hp, 60)
                self.assertEqual(case["characters"][7]["hp"], actor.hp)
                self.assertTrue(snapshot_characteristics(actor))
                self.assertTrue(
                    snapshot_characteristics(case["runtime"].fight.actors[-200])
                )


if __name__ == "__main__":
    unittest.main()
