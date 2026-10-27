"""Opt-in complete-context transport; retains the existing native protocol."""
import io
import json
import time
import urllib.error

from ..bridge.world_bridge import ContextTransport, _json_bytes
from ..native.native_deadline import check, remaining
from .framed import FramedClient


class FramedContextTransport(ContextTransport):
    """Replace HTTP framing only; snapshots, hashes and retries stay shared."""

    def __init__(self, host, port, *, timeout=10, **options):
        super().__init__(f"tcp://{host}:{port}", timeout=timeout, **options)
        self.channel = FramedClient(host, port, timeout=timeout)

    def close(self):
        channel = getattr(self, "channel", None)
        if channel is not None:
            channel.close()

    def __del__(self):
        channel = getattr(self, "channel", None)
        if channel is not None:
            channel.close()

    def request(self, endpoint, payload):
        check()
        available = remaining()
        deadline = None if available is None else time.monotonic() + available
        started = time.monotonic()
        opens = self.channel.tcp_opens
        sent = self.channel.sent_payload_bytes
        self.metrics["requests"] += 1
        try:
            status, result = self.channel.request(endpoint, payload, deadline=deadline)
            self.metrics["receivedBytes"] += len(_json_bytes(result))
            check()
            if status >= 400:
                # Match the existing HTTP adapter: errors do not retain an
                # owner channel for a later retry or a different request.
                self.close()
                raise urllib.error.HTTPError(
                    self.url + endpoint,
                    status,
                    "AI channel request failed",
                    {},
                    io.BytesIO(json.dumps(result).encode()),
                )
            return result
        finally:
            self.metrics["sentBytes"] += self.channel.sent_payload_bytes - sent
            self.metrics["tcpOpens"] += self.channel.tcp_opens - opens
            self.metrics["requestSeconds"] += time.monotonic() - started
