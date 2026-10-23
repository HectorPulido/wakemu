"""Bounded persistent TCP request frames; no planner or game rules live here."""
import json
import math
import socket
import struct
import threading
import time

MAX_FRAME = 4 * 1024 * 1024


def _constant(value):
    raise ValueError("Non-finite JSON number")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def encode_frame(value, *, maximum=MAX_FRAME):
    body = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
    if not 0 < len(body) <= maximum:
        raise ValueError("Invalid AI frame size")
    return struct.pack("!I", len(body)) + body


def _timeout(peer, deadline):
    timeout = deadline - time.monotonic()
    if timeout <= 0:
        raise TimeoutError("AI frame deadline reached")
    peer.settimeout(timeout)


def _read(peer, size, deadline):
    chunks = []
    while size:
        _timeout(peer, deadline)
        chunk = peer.recv(min(size, 65536))
        if not chunk:
            raise ConnectionError("Incomplete AI frame")
        chunks.append(chunk)
        size -= len(chunk)
    return b"".join(chunks)


def read_frame(peer, deadline, *, maximum=MAX_FRAME):
    size = struct.unpack("!I", _read(peer, 4, deadline))[0]
    if not 0 < size <= maximum:
        raise ValueError("Invalid AI frame size")
    return json.loads(
        _read(peer, size, deadline),
        parse_constant=_constant,
        object_pairs_hook=_object,
    )


def write_frame(peer, value, deadline, *, maximum=MAX_FRAME):
    frame = encode_frame(value, maximum=maximum)
    _timeout(peer, deadline)
    peer.sendall(frame)
    if time.monotonic() >= deadline:
        raise TimeoutError("AI frame deadline reached")
    return len(frame)


class FramedClient:
    """One serial channel per owner; failures close it without replaying work."""

    def __init__(self, host, port, *, timeout=10, maximum=MAX_FRAME):
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or not 0 < timeout <= 120
            or type(maximum) is not int
            or not 1 <= maximum <= MAX_FRAME
        ):
            raise ValueError("Invalid AI channel limits")
        self.address = (host, port)
        self.timeout, self.maximum = timeout, maximum
        self._peer = None
        self._sequence = 0
        self._lock = threading.Lock()
        self.tcp_opens = 0

    def close(self):
        peer, self._peer = self._peer, None
        if peer is not None:
            peer.close()

    def request(self, endpoint, payload, *, deadline=None):
        if deadline is not None and (
            type(deadline) not in (int, float) or not math.isfinite(deadline)
        ):
            raise ValueError("Invalid AI channel deadline")
        deadline = min(
            float("inf") if deadline is None else deadline,
            time.monotonic() + self.timeout,
        )
        available = deadline - time.monotonic()
        if available <= 0 or not self._lock.acquire(timeout=available):
            raise TimeoutError("AI channel deadline reached")
        try:
            try:
                if self._peer is None:
                    available = deadline - time.monotonic()
                    if available <= 0:
                        raise TimeoutError("AI channel deadline reached")
                    peer = socket.create_connection(self.address, timeout=available)
                    peer.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    self._peer = peer
                    self.tcp_opens += 1
                self._sequence += 1
                identity = self._sequence
                write_frame(
                    self._peer,
                    dict(id=identity, endpoint=endpoint, payload=payload),
                    deadline,
                    maximum=self.maximum,
                )
                reply = read_frame(self._peer, deadline, maximum=self.maximum)
                if time.monotonic() >= deadline:
                    raise TimeoutError("AI channel deadline reached")
                if (
                    not isinstance(reply, dict)
                    or set(reply) != {"id", "status", "payload"}
                    or type(reply["id"]) is not int
                    or reply["id"] != identity
                    or type(reply["status"]) is not int
                    or not 100 <= reply["status"] <= 599
                ):
                    raise ValueError("Foreign or malformed AI channel response")
                return reply["status"], reply["payload"]
            except BaseException:
                self.close()
                raise
        finally:
            self._lock.release()
