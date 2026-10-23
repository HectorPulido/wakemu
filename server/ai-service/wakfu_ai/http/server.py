#!/usr/bin/env python3
"""Separate, dependency-free HTTP boundary for the existing Wakfu AI planner."""
import json
import base64
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ..planning.planner import decide
from ..planning.query_sessions import QuerySessions
from ..context.context_store import ContextStore
from .capacity import capacities


MAX_BODY = 4 * 1024 * 1024
MAX_DECISIONS, MAX_CONNECTIONS = capacities()
DECISIONS = threading.BoundedSemaphore(MAX_DECISIONS)
_CONTEXT_STORE = None
_CONTEXT_LOCK = threading.Lock()
_QUERY_SESSIONS = QuerySessions(capacity=MAX_DECISIONS)


def context_store():
    global _CONTEXT_STORE
    with _CONTEXT_LOCK:
        if _CONTEXT_STORE is None:
            _CONTEXT_STORE = ContextStore(
                os.environ.get("WAKFU_AI_CONTEXT_ROOT", "/tmp/wakfu-ai-context")
            )
        return _CONTEXT_STORE


def context_request(path, payload):
    if not isinstance(payload, dict):
        raise ValueError("Invalid complete context request")
    store = context_store()
    if path == "/v3/context/block":
        if set(payload) != {"sha256", "size", "offset", "data"} or not isinstance(
            payload["data"], str
        ):
            raise ValueError("Invalid complete context block fields")
        try:
            data = base64.b64decode(payload["data"], validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError("Invalid complete context block encoding") from error
        return store.put(payload["sha256"], payload["size"], payload["offset"], data)
    if path == "/v3/context/status":
        if set(payload) != {"objects"} or not isinstance(payload["objects"], list):
            raise ValueError("Invalid complete context status fields")
        present, seen = [], {}
        for entry in payload["objects"]:
            if (
                not isinstance(entry, dict)
                or set(entry) != {"sha256", "size"}
                or type(entry["size"]) is not int
                or entry["size"] < 0
            ):
                raise ValueError("Invalid complete context object descriptor")
            digest = entry["sha256"]
            store._path(digest)
            if digest in seen:
                if seen[digest] != entry["size"]:
                    raise ValueError("Conflicting complete context object sizes")
                continue
            seen[digest] = entry["size"]
            if store.has(digest, entry["size"]):
                present.append(digest)
        return dict(present=sorted(present))
    if set(payload) != {"sha256"}:
        raise ValueError("Invalid complete context manifest fields")
    if path == "/v3/context/seal":
        return store.seal_manifest(payload["sha256"])
    return store.manifest(payload["sha256"])


class BoundedHTTPServer(ThreadingHTTPServer):
    """Bound sockets as well as CPU decisions, including incomplete headers."""

    request_queue_size = MAX_CONNECTIONS

    def __init__(self, address, handler, *, max_connections=MAX_CONNECTIONS):
        if type(max_connections) is not int or not 1 <= max_connections <= 128:
            raise ValueError("Invalid AI connection capacity")
        self.connections = threading.BoundedSemaphore(max_connections)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        # Headers and small JSON bodies are separate writes. Nagle combined
        # with delayed ACK otherwise adds ~40 ms to persistent round trips.
        request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        request.settimeout(5)
        if not self.connections.acquire(blocking=False):
            try:
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"
                )
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.connections.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connections.release()


def _invalid_constant(value):
    raise ValueError("Non-finite JSON number")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, status, payload):
        data = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        keepalive = (
            getattr(self, "complete_request_body", False)
            and self.headers.get("X-Wakfu-Keepalive") == "1"
            and status == 200
        )
        self.send_header("Connection", "keep-alive" if keepalive else "close")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            # An owner can abandon a negotiation at its deadline. The search
            # is cancelled separately; a disconnected HTTP peer is expected.
            pass
        self.close_connection = not keepalive

    def do_GET(self):
        if self.path == "/health":
            self._json(
                200,
                dict(
                    status="ok",
                    service="wakfu-ai",
                    protocol=1,
                    protocols=[1, 2, 3],
                    capacity=dict(decisions=MAX_DECISIONS, connections=MAX_CONNECTIONS),
                ),
            )
        else:
            self._json(404, dict(error="Unknown AI endpoint"))

    def do_POST(self):
        self.complete_request_body = False
        if self.path not in (
            "/v1/decide",
            "/v2/decide",
            "/v3/decide",
            "/v3/cancel",
            "/v3/context/block",
            "/v3/context/status",
            "/v3/context/manifest",
            "/v3/context/seal",
            "/v3/context/continue",
        ):
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
            self.complete_request_body = True
            snapshot = json.loads(
                body, parse_constant=_invalid_constant, object_pairs_hook=_object
            )
            if self.path == "/v2/decide" and (
                not isinstance(snapshot, dict)
                or type(snapshot.get("protocol")) is not int
                or snapshot["protocol"] != 2
            ):
                raise ValueError("Endpoint requires AI protocol 2")
            if not DECISIONS.acquire(blocking=False):
                self._json(503, dict(error="AI decision capacity reached"))
                return
            try:
                if self.path == "/v3/decide":
                    result = _QUERY_SESSIONS.decide(snapshot, context_store())
                elif self.path == "/v3/cancel":
                    result = _QUERY_SESSIONS.cancel(snapshot)
                elif self.path == "/v3/context/continue":
                    from ..transport.context_bundle import continue_request

                    result = continue_request(
                        snapshot, context_store(), _QUERY_SESSIONS
                    )
                elif self.path.startswith("/v3/context/"):
                    result = context_request(self.path, snapshot)
                else:
                    result = decide(snapshot)
            finally:
                DECISIONS.release()
        except (ValueError, UnicodeDecodeError, RecursionError) as error:
            self._json(400, dict(error=str(error)))
            return
        except TimeoutError:
            self._json(408, dict(error="AI request timed out"))
            return
        except OSError:
            self._json(503, dict(error="Complete context storage unavailable"))
            return
        self._json(200, result)

    def log_message(self, format, *args):
        # Keep snapshots/account state out of HTTP logs.
        return


def main():
    # Stable legacy import path; production no longer creates an HTTP server.
    from ..transport.framed_server import main as tcp_main

    tcp_main()


if __name__ == "__main__":
    main()
