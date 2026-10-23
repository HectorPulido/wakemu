"""TCP-only endpoint for the separate native AI service.

Nothing binds or starts on import. Production owns one bounded TCP listener.
"""
import socket
import json
import math
import os
import socketserver
import threading
import time

from ..http import server as http
from ..native.native_deadline import bounded, remaining
from .framed import MAX_FRAME, read_frame, write_frame
from .startup_readiness import DEFAULT_MANIFEST, seal_bootstrap_catalog


def _processing_deadline(endpoint, frame_deadline):
    # Cold catalog sealing is administrative work. It previously had a
    # 120-second HTTP client budget; native planning and idle reads retain
    # their normal limits. A nested owner deadline can only narrow this.
    now = time.monotonic()
    deadline = now + 120 if endpoint == "/v3/context/seal" else frame_deadline
    available = remaining()
    return deadline if available is None else min(deadline, now + available)


def dispatch(endpoint, payload):
    """Use the existing registries, context checks and decision capacity."""
    if endpoint == "/health":
        return 200, dict(
            status="ok",
            service="wakfu-ai",
            protocol=1,
            protocols=[1, 2, 3],
            transport="tcp",
            capacity=dict(
                decisions=http.MAX_DECISIONS, connections=http.MAX_CONNECTIONS
            ),
        )
    if endpoint not in (
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
        return 404, dict(error="Unknown AI endpoint")
    if not http.DECISIONS.acquire(blocking=False):
        return 503, dict(error="AI decision capacity reached")
    try:
        if endpoint == "/v2/decide" and (
            not isinstance(payload, dict)
            or type(payload.get("protocol")) is not int
            or payload["protocol"] != 2
        ):
            raise ValueError("Endpoint requires AI protocol 2")
        if endpoint in ("/v1/decide", "/v2/decide"):
            result = http.decide(payload)
        elif endpoint == "/v3/decide":
            result = http._QUERY_SESSIONS.decide(payload, http.context_store())
        elif endpoint == "/v3/cancel":
            result = http._QUERY_SESSIONS.cancel(payload)
        elif endpoint == "/v3/context/continue":
            from .context_bundle import continue_request

            result = continue_request(
                payload, http.context_store(), http._QUERY_SESSIONS
            )
        else:
            result = http.context_request(endpoint, payload)
        return 200, result
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        return 400, dict(error=str(error))
    except TimeoutError:
        return 408, dict(error="AI request timed out")
    except OSError:
        return 503, dict(error="Complete context storage unavailable")
    finally:
        http.DECISIONS.release()


class FramedHandler(socketserver.BaseRequestHandler):
    def handle(self):
        previous = 0
        while True:
            deadline = time.monotonic() + self.server.request_timeout
            try:
                message = read_frame(
                    self.request, deadline, maximum=self.server.maximum
                )
                if (
                    not isinstance(message, dict)
                    or set(message) != {"id", "endpoint", "payload"}
                    or type(message["id"]) is not int
                    or message["id"] <= previous
                    or not isinstance(message["endpoint"], str)
                    or not isinstance(message["payload"], dict)
                ):
                    raise ValueError("Invalid AI channel request")
                previous = message["id"]
                deadline = _processing_deadline(message["endpoint"], deadline)
                with bounded(deadline):
                    status, payload = self.server.dispatch(
                        message["endpoint"], message["payload"]
                    )
                write_frame(
                    self.request,
                    dict(id=previous, status=status, payload=payload),
                    deadline,
                    maximum=self.server.maximum,
                )
            except (OSError, ValueError, ConnectionError):
                # Incomplete/oversized/expired channels have no reusable frame
                # boundary. A reconnect starts a fresh owner channel.
                return


class FramedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False

    def __init__(
        self,
        address,
        *,
        dispatcher=dispatch,
        max_connections=http.MAX_CONNECTIONS,
        request_timeout=30,
        maximum=MAX_FRAME,
        connections=None,
    ):
        if type(max_connections) is not int or not 1 <= max_connections <= 128:
            raise ValueError("Invalid AI connection capacity")
        if (
            type(request_timeout) not in (int, float)
            or not math.isfinite(request_timeout)
            or not 0 < request_timeout <= 60
            or type(maximum) is not int
            or not 1 <= maximum <= MAX_FRAME
        ):
            raise ValueError("Invalid AI channel limits")
        self.dispatch, self.request_timeout, self.maximum = (
            dispatcher,
            request_timeout,
            maximum,
        )
        # The HTTP owner can pass its own semaphore so both listeners share
        # one total connection limit instead of doubling configured capacity.
        self.connections = (
            threading.BoundedSemaphore(max_connections)
            if connections is None
            else connections
        )
        self.request_queue_size = max_connections
        super().__init__(address, FramedHandler)

    def process_request(self, request, address):
        request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        if not self.connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.connections.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.connections.release()


def main():
    host = os.environ.get("WAKFU_AI_BIND", "0.0.0.0")
    port = int(os.environ.get("WAKFU_AI_PORT", "8090"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid AI TCP listener port")
    # TCP health becomes reachable only after the serving store owns the
    # immutable full catalogue. No player turn pays this cold sealing cost.
    ready = seal_bootstrap_catalog(
        http.context_store(),
        os.environ.get("WAKFU_AI_BOOTSTRAP_MANIFEST", DEFAULT_MANIFEST),
    )
    print(json.dumps(dict(event="ai_catalog_ready", **ready)), flush=True)
    server = FramedServer((host, port))
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
