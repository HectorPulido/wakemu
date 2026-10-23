"""World negotiation owns and clears context attachments across all exits."""
import unittest

import test_native_partial_decision as partial_fixture
from wakfu_ai.native.native_deadline import bounded


class NativeBundleLifecycleTests(unittest.TestCase):
    def fixture(self):
        helper = partial_fixture.PartialDecisionTests()
        values = helper.fixture()
        _, _, transport, session, _, _ = values
        transport.pending = None
        transport.sent = []
        transport.aborts = 0
        legacy_rpc, original_query = transport._retry_request, session._query

        def begin():
            self.assertIsNone(transport.pending)
            transport.pending = []

        def abort():
            transport.aborts += 1
            transport.pending = None

        def continuation(payload):
            transport.sent.append((payload, tuple(transport.pending or ())))
            result = legacy_rpc("/v3/decide", payload)
            transport.pending = None
            return result

        def query(operation, key, payload):
            transport.pending.append(payload["id"])
            return original_query(operation, key, payload)

        transport.begin_context_bundle = begin
        transport.abort_context_bundle = abort
        transport.continue_with_context = continuation
        session._query = query
        return values

    def test_timeout_clears_attachment_queue_before_fresh_recertification(self):
        _, oracle, transport, session, now, _ = self.fixture()
        original = oracle.preview

        def preview(runtime, action):
            if len(oracle.preview_calls) == 1:
                self.assertIsNone(transport.pending)
            return original(runtime, action)

        oracle.preview = preview
        with bounded(1.2, clock=lambda: now[0]):
            result = session.decide(certify=False)
        self.assertEqual(result["plan"], [partial_fixture.MOVE])
        self.assertEqual(
            [attachments for _, attachments in transport.sent], [(), ("1",), ("2",)]
        )
        self.assertIsNone(transport.pending)
        self.assertEqual(transport.aborts, 1)
        self.assertEqual(len(oracle.preview_calls), 2)

    def test_unsupported_native_query_discards_all_staged_context(self):
        _, _, transport, session, now, _ = self.fixture()

        def unsupported(operation, key, query):
            transport.pending.extend(["private-incomplete-context", query["id"]])
            raise ValueError("fixture_native_unavailable")

        session._query = unsupported
        with bounded(1.2, clock=lambda: now[0]):
            result = session.decide(certify=False)
        self.assertEqual(result["action"], dict(type="end_turn"))
        self.assertTrue(all(not attachments for _, attachments in transport.sent))
        self.assertIsNone(transport.pending)

    def test_native_query_exception_aborts_bundle_without_another_rpc(self):
        _, _, transport, session, now, _ = self.fixture()

        def broken(operation, key, query):
            transport.pending.append("incomplete-private-context")
            raise RuntimeError("native candidate computation failed")

        session._query = broken
        with bounded(1.2, clock=lambda: now[0]):
            with self.assertRaisesRegex(RuntimeError, "computation failed"):
                session.decide(certify=False)
        self.assertEqual(len(transport.sent), 1)
        self.assertEqual(transport.aborts, 1)
        self.assertIsNone(transport.pending)

    def test_explicit_cancel_clears_queued_context_before_legacy_cancel_rpc(self):
        _, _, transport, session, _, _ = self.fixture()
        transport.begin_context_bundle()
        transport.pending.append("never-published")

        def cancel_rpc(endpoint, payload):
            self.assertEqual(endpoint, "/v3/cancel")
            self.assertIsNone(transport.pending)
            return dict(status="cancelled")

        transport.request = cancel_rpc
        session.cancel()
        self.assertIsNone(transport.pending)
        self.assertEqual(transport.aborts, 1)

    def test_legacy_transport_without_bundle_capability_still_recovers(self):
        _, oracle, _, session, now, _ = partial_fixture.PartialDecisionTests().fixture()
        with bounded(1.2, clock=lambda: now[0]):
            result = session.decide(certify=False)
        self.assertEqual(result["action"], partial_fixture.MOVE)
        self.assertEqual(len(oracle.preview_calls), 2)
