#!/usr/bin/env python3
"""Separate, dependency-free HTTP boundary for the existing Wakfu AI planner."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from planner import decide

MAX_BODY = 4 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, status, payload):
        data = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def do_GET(self):
        if self.path == "/health":
            self._json(200, dict(status="ok", service="wakfu-ai", protocol=1))
        else:
            self._json(404, dict(error="Unknown AI endpoint"))

    def do_POST(self):
        if self.path != "/v1/decide":
            self._json(404, dict(error="Unknown AI endpoint"))
            return
        if self.headers.get("Transfer-Encoding"):
            self._json(400, dict(error="Chunked requests are unsupported"))
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            self._json(400, dict(error="Invalid Content-Length"))
            return
        if not 0 < length <= MAX_BODY:
            self._json(
                413 if length > MAX_BODY else 400, dict(error="Invalid request size")
            )
            return
        self.connection.settimeout(5)
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete request body")
            snapshot = json.loads(body)
            result = decide(snapshot)
        except (ValueError, UnicodeDecodeError) as error:
            self._json(400, dict(error=str(error)))
            return
        except TimeoutError:
            self._json(408, dict(error="AI request timed out"))
            return
        self._json(200, result)

    def log_message(self, format, *args):
        # Keep snapshots/account state out of HTTP logs.
        return


def main():
    host = os.environ.get("WAKFU_AI_BIND", "0.0.0.0")
    port = int(os.environ.get("WAKFU_AI_PORT", "8090"))
    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
