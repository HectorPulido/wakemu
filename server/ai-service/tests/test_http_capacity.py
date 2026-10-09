"""Verify configurable limits and sixteen genuinely concurrent HTTP requests."""
import json
import socket
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from unittest.mock import patch

from wakfu_ai.http.capacity import capacities
from wakfu_ai.http import server as boundary


class CapacityTests(unittest.TestCase):
    def test_defaults_overrides_and_invalid_configuration(self):
        self.assertEqual(capacities({}), (16, 64))
        self.assertEqual(
            capacities(
                {"WAKFU_AI_MAX_DECISIONS": "32", "WAKFU_AI_MAX_CONNECTIONS": "96"}
            ),
            (32, 96),
        )
        for settings in (
            {"WAKFU_AI_MAX_DECISIONS": "0"},
            {"WAKFU_AI_MAX_DECISIONS": "65"},
            {"WAKFU_AI_MAX_CONNECTIONS": "129"},
            {"WAKFU_AI_MAX_CONNECTIONS": "invalid"},
            {"WAKFU_AI_MAX_CONNECTIONS": "8"},
        ):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                capacities(settings)

    def test_sixteen_requests_run_together_and_seventeenth_is_rejected(self):
        all_entered, release = threading.Event(), threading.Event()
        counter_lock = threading.Lock()
        entered = 0

        def blocked_request(path, payload):
            nonlocal entered
            with counter_lock:
                entered += 1
                if entered == 16:
                    all_entered.set()
            if not release.wait(5):
                raise RuntimeError("Concurrent requests did not get released")
            return {"present": []}

        http = boundary.BoundedHTTPServer(("127.0.0.1", 0), boundary.Handler)
        worker = threading.Thread(target=http.serve_forever, daemon=True)
        worker.start()

        def request():
            connection = HTTPConnection(*http.server_address, timeout=6)
            try:
                connection.request(
                    "POST",
                    "/v3/context/status",
                    json.dumps({"objects": []}),
                    {"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                response.read()
                return response.status
            finally:
                connection.close()

        try:
            with patch.object(
                boundary, "context_request", blocked_request
            ), patch.object(
                boundary, "DECISIONS", threading.BoundedSemaphore(16)
            ), ThreadPoolExecutor(
                max_workers=16
            ) as executor:
                futures = [executor.submit(request) for _ in range(16)]
                try:
                    self.assertTrue(
                        all_entered.wait(4), "Only eight workers would stall here"
                    )
                    self.assertEqual(request(), 503)
                finally:
                    release.set()
                self.assertEqual([future.result() for future in futures], [200] * 16)
                self.assertEqual(request(), 200)
        finally:
            release.set()
            http.shutdown()
            http.server_close()
            worker.join(2)

    def test_search_registry_and_http_use_the_same_capacity(self):
        self.assertEqual(boundary._QUERY_SESSIONS.capacity, boundary.MAX_DECISIONS)

    def test_accepted_socket_disables_nagle_for_small_keepalive_responses(self):
        options = []

        class ObservedHandler(boundary.Handler):
            def handle(self):
                options.append(
                    self.request.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
                )
                super().handle()

        http = boundary.BoundedHTTPServer(("127.0.0.1", 0), ObservedHandler)
        worker = threading.Thread(target=http.serve_forever, daemon=True)
        worker.start()
        connection = HTTPConnection(*http.server_address, timeout=2)
        try:
            connection.request("GET", "/health")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            response.read()
            self.assertEqual(len(options), 1)
            self.assertTrue(options[0])
        finally:
            connection.close()
            http.shutdown()
            http.server_close()
            worker.join(2)
