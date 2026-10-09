"""Cold preparation phases remain observable, including failed captures."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_ai.bridge.world_bridge import NativeSession


class PreparationMetricTests(unittest.TestCase):
    def session_arguments(self):
        class Oracle:
            runtime = SimpleNamespace(fight=SimpleNamespace())
            flags = {}

            def authorities(self):
                return {}

            def complete_state_bytes(self, runtime):
                return b"complete context bytes"

            def state_identity(self, runtime):
                return "runtime identity"

        class Transport:
            metrics = {}

            def catalog(self, exporter):
                return "c" * 64

            def instance_bytes(self, body):
                self.body = body
                return "d" * 64

        return Oracle(), Transport(), object()

    def test_success_reports_catalog_source_encoding_publication_and_identity(self):
        oracle, transport, exporter = self.session_arguments()
        session = NativeSession(
            oracle,
            transport,
            exporter,
            policy={},
            policy_version="test",
            fight_instance_id="test",
        )
        phases = transport.metrics["nativeSessionPreparationMs"]
        self.assertIs(phases, session.preparation_stages_ms)
        self.assertEqual(
            set(phases),
            {
                "catalog_transfer",
                "source_hash",
                "root_register",
                "state_encoding",
                "state_publication",
                "runtime_identity",
            },
        )
        self.assertTrue(all(value >= 0 for value in phases.values()))
        self.assertEqual(transport.body, b"complete context bytes")

    def test_failed_catalog_capture_retains_phase_without_changing_error(self):
        oracle, transport, exporter = self.session_arguments()
        error = TimeoutError("cold source deadline")

        def failed(exporter):
            raise error

        transport.catalog = failed
        with self.assertRaises(TimeoutError) as caught:
            NativeSession(
                oracle,
                transport,
                exporter,
                policy={},
                policy_version="test",
                fight_instance_id="test",
            )
        self.assertIs(caught.exception, error)
        self.assertEqual(
            set(transport.metrics["nativeSessionPreparationMs"]), {"catalog_transfer"}
        )

    def test_complete_catalogue_reuse_is_scoped_to_turn_exporter_endpoint_and_fight(
        self,
    ):
        from wakfu_ai.bridge.world_bridge import turn_catalogue_scope

        oracle, transport, exporter = self.session_arguments()
        calls = []
        transport.url = "http://first-ai"
        transport.catalog = lambda source: (calls.append(source) or "c" * 64)

        def prepare(fight="same-fight", source=exporter):
            return NativeSession(
                oracle,
                transport,
                source,
                policy={},
                policy_version="same-policy",
                fight_instance_id=fight,
            )

        with turn_catalogue_scope():
            first = prepare()
            second = prepare()
            self.assertEqual(len(calls), 1)
            self.assertEqual(first.catalog, second.catalog)
            self.assertNotIn("catalog_transfer", second.preparation_stages_ms)
            self.assertIn("source_hash", second.preparation_stages_ms)
            self.assertIn("root_register", second.preparation_stages_ms)
            prepare("another-fight")
            prepare(source=object())
            transport.url = "http://another-ai"
            prepare()
            self.assertEqual(len(calls), 4)
        prepare()
        self.assertEqual(len(calls), 5)
        with turn_catalogue_scope():
            prepare()
            self.assertEqual(len(calls), 6)


class NativeQueryMetricTests(unittest.TestCase):
    def test_query_metrics_measure_success_and_failure_without_payloads(self):
        session = NativeSession.__new__(NativeSession)
        session.native_query_metrics = {}
        result = object()
        session._query_unmeasured = lambda operation, key, request: result
        self.assertIs(
            session._query(
                "preview", "state", {"action": {"type": "move", "path": [[1, 2, 3]]}}
            ),
            result,
        )
        error = ValueError("native unsupported")

        def failed(operation, key, request):
            raise error

        session._query_unmeasured = failed
        with self.assertRaises(ValueError) as caught:
            session._query("preview", "state", {"action": {"type": "move"}})
        self.assertIs(caught.exception, error)
        metric = session.native_query_metrics["preview:move"]
        self.assertEqual(metric["calls"], 2)
        self.assertEqual(metric["failures"], 1)
        self.assertEqual(
            set(metric), {"calls", "failures", "wallMs", "threadCpuMs", "maxWallMs"}
        )
        self.assertTrue(all(value >= 0 for value in metric.values()))


class DiagnosticSnapshotTests(unittest.TestCase):
    def test_later_queries_do_not_change_already_delivered_nested_metrics(self):
        from wakfu_ai.bridge import world_entry

        runtime = SimpleNamespace(
            fight=SimpleNamespace(id=1, current=SimpleNamespace(id=-1))
        )
        authorities = dict(
            characters={1: {"id": 1}},
            monsters={},
            decks={1: b""},
            excluded_decks={1: frozenset()},
            viewer_id=1,
            registrations={},
        )
        transport = SimpleNamespace(
            metrics={
                "nativeQueryMetrics": {"preview:move": {"calls": 1, "wallMs": 2.0}}
            },
            close=lambda: None,
        )

        def deliveries(runtime, **kwargs):
            yield [], {"action": {"type": "move"}}
            transport.metrics["nativeQueryMetrics"]["preview:move"]["calls"] = 7
            yield [], {"action": {"type": "end_turn"}}

        with patch.object(
            world_entry, "load_authorities", return_value=authorities
        ), patch.object(
            world_entry,
            "encounter_profiles",
            return_value={None: {"policy": {}, "identity": "test"}},
        ), patch.object(
            world_entry, "ContextTransport", return_value=transport
        ), patch.object(
            world_entry, "NativeStats", return_value=object()
        ), patch.object(
            world_entry, "native_exporter", return_value=object()
        ), patch.object(
            world_entry, "run_turn", deliveries
        ):
            received = list(
                world_entry._run_npc_turn(
                    runtime,
                    store=None,
                    viewer_character={"id": 1},
                    monsters={},
                    stats_serializer=None,
                )
            )
        first = received[0][1]["transportMetrics"]["nativeQueryMetrics"]["preview:move"]
        second = received[1][1]["transportMetrics"]["nativeQueryMetrics"][
            "preview:move"
        ]
        self.assertEqual(first["calls"], 1)
        self.assertEqual(second["calls"], 7)
        self.assertIsNot(first, second)
