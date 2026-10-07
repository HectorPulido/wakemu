"""Operational boundary: slow clients cannot create unlimited handler threads."""
import socket
import threading
import unittest
from http.client import HTTPConnection
from server import BoundedHTTPServer, Handler


class ConnectionCapacityTests(unittest.TestCase):
    def test_incomplete_headers_are_bounded_and_slots_are_released(self):
        accepted = threading.Event()

        class ObservedHandler(Handler):
            def handle(self):
                accepted.set()
                super().handle()

        server = BoundedHTTPServer(("127.0.0.1", 0), ObservedHandler, max_connections=1)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        held = socket.create_connection(server.server_address, timeout=2)
        try:
            held.sendall(b"GET /health HTTP/1.1\r\n")
            self.assertTrue(accepted.wait(2))
            client = HTTPConnection(*server.server_address, timeout=2)
            try:
                client.request("GET", "/health")
                response = client.getresponse()
                self.assertEqual(response.status, 503)
                response.read()
            finally:
                client.close()
            held.sendall(b"Host: localhost\r\n\r\n")
            received = bytearray()
            while True:
                data = held.recv(4096)
                if not data:
                    break
                received.extend(data)
            self.assertIn(b"200 OK", received)
            # Closing delivery frees the worker slot. Acquiring the semaphore
            # waits for completion without racing the next request.
            self.assertTrue(server.connections.acquire(timeout=2))
            server.connections.release()
            client = HTTPConnection(*server.server_address, timeout=2)
            try:
                client.request("GET", "/health")
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
            finally:
                client.close()
        finally:
            held.close()
            server.shutdown()
            server.server_close()
            worker.join(2)


if __name__ == "__main__":
    unittest.main()
