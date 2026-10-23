"""Legacy World callers use the same framed service and fail closed."""
import os
import threading
import unittest
from unittest.mock import patch

from test_tactical import snapshot
from wakfu_ai.http import server as http
from wakfu_ai.transport.framed_server import FramedServer
from wakfu_server.combat_ai_transport import request


class WorldTcpClientTests(unittest.TestCase):
    def serve(self, **kwargs):
        server = FramedServer(("127.0.0.1", 0), **kwargs)
        worker = threading.Thread(
            target=server.serve_forever, kwargs=dict(poll_interval=0.01), daemon=True
        )
        worker.start()
        self.addCleanup(worker.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        environment = patch.dict(
            os.environ,
            {"WAKFU_AI_URL": "tcp://127.0.0.1:" + str(server.server_address[1])},
        )
        environment.start()
        self.addCleanup(environment.stop)
        return server

    def test_real_world_legacy_request_preserves_both_planner_protocols(self):
        self.serve()
        for protocol in (1, 2):
            with self.subTest(protocol=protocol):
                payload = dict(snapshot(), protocol=protocol)
                actual = request("/v%s/decide" % protocol, payload)
                expected = http.decide(payload)
                for field in ("protocol", "requestId", "stateKey", "decision"):
                    self.assertEqual(actual.get(field), expected.get(field))

    def test_legacy_http_address_still_uses_only_framed_tcp_bytes(self):
        server = self.serve()
        with patch.dict(
            os.environ,
            {"WAKFU_AI_URL": "http://127.0.0.1:" + str(server.server_address[1])},
        ), patch("urllib.request.urlopen") as urlopen, patch(
            "http.client.HTTPConnection"
        ) as http_connection:
            payload = dict(snapshot(), protocol=1)
            self.assertEqual(request("/v1/decide", payload), http.decide(payload))
            urlopen.assert_not_called()
            http_connection.assert_not_called()

    def test_rejected_status_never_becomes_a_tactical_response(self):
        self.serve()
        for endpoint, payload in (
            ("/missing", {}),
            ("/v2/decide", dict(snapshot(), protocol=True)),
        ):
            with self.subTest(endpoint=endpoint):
                with self.assertRaisesRegex(ValueError, "rejected"):
                    request(endpoint, payload)

    def test_world_client_enforces_complete_response_limit(self):
        self.serve(
            dispatcher=lambda endpoint, payload: (200, dict(data="x" * (1024 * 1024)))
        )
        with self.assertRaisesRegex(ValueError, "size limit"):
            request("/v1/decide", {})

    def test_wire_loss_is_reported_without_replaying_decision(self):
        observed = []

        def broken(endpoint, payload):
            observed.append(payload)
            raise ConnectionError("fixture disconnected before reply")

        self.serve(dispatcher=broken)
        with self.assertRaises((OSError, ConnectionError)):
            request("/v1/decide", dict(requestId="one-shot"))
        self.assertEqual(observed, [dict(requestId="one-shot")])
