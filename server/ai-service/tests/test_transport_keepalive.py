"""Persistent transport lifetime, retry framing and absolute request limits."""
import json
import threading
import time
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler
from wakfu_ai.bridge.world_bridge import ContextTransport
from wakfu_ai.http.server import BoundedHTTPServer, Handler
from wakfu_ai.native.native_deadline import bounded


class PersistentTransportTests(unittest.TestCase):
    def listener(self, handler=Handler, *, capacity=1):
        server = BoundedHTTPServer(("127.0.0.1", 0), handler, max_connections=capacity)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def test_same_socket_is_reused_and_close_releases_capacity(self):
        server = self.listener()
        client = ContextTransport("http://%s:%s" % server.server_address)
        self.addCleanup(client.close)
        for _ in range(3):
            self.assertEqual(
                client.request("/v3/context/status", {"objects": []}), {"present": []}
            )
        self.assertEqual(client.metrics["requests"], 3)
        self.assertEqual(client.metrics["tcpOpens"], 1)
        client.close()
        self.assertTrue(server.connections.acquire(timeout=2))
        server.connections.release()
        self.assertEqual(
            client.request("/v3/context/status", {"objects": []}), {"present": []}
        )
        self.assertEqual(client.metrics["tcpOpens"], 2)

    def test_abandoned_transport_releases_its_owned_socket(self):
        server = self.listener()
        client = ContextTransport("http://%s:%s" % server.server_address)
        client.request("/v3/context/status", {"objects": []})
        del client
        self.assertTrue(server.connections.acquire(timeout=2))
        server.connections.release()

    def test_error_closes_socket_and_next_request_reconnects(self):
        server = self.listener()
        client = ContextTransport("http://%s:%s" % server.server_address)
        self.addCleanup(client.close)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            client.request("/v3/context/status", {"invalid": []})
        self.assertEqual(caught.exception.code, 400)
        self.assertIsNone(client._connection)
        self.assertEqual(
            client.request("/v3/context/status", {"objects": []}), {"present": []}
        )
        self.assertEqual(client.metrics["tcpOpens"], 2)

    def test_idle_keepalive_is_expired_and_releases_capacity(self):
        class ShortIdleHandler(Handler):
            def do_POST(self):
                super().do_POST()
                self.connection.settimeout(0.1)

        server = self.listener(ShortIdleHandler)
        client = ContextTransport("http://%s:%s" % server.server_address)
        self.addCleanup(client.close)
        client.request("/v3/context/status", {"objects": []})
        self.assertTrue(server.connections.acquire(timeout=1))
        server.connections.release()

    def test_dripping_body_cannot_extend_native_absolute_deadline(self):
        class Drip(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                body = json.dumps({"value": "x" * 100}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    for byte in body:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.02)
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        server = self.listener(Drip)
        client = ContextTransport("http://%s:%s" % server.server_address, timeout=2)
        self.addCleanup(client.close)
        started = time.monotonic()
        with bounded(started + 0.15):
            with self.assertRaises(TimeoutError):
                client.request("/drip", {})
        self.assertLess(time.monotonic() - started, 0.7)
        self.assertIsNone(client._connection)


if __name__ == "__main__":
    unittest.main()
