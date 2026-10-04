"""Notify native clients before terminating their dispatcher/world channels.

Np18 carries Uw16 SERVER_SHUTDOWN. cgW stores the reason; cgI handles the
subsequent channel-close event by restoring the login handlers and UI.
No reconnect token, official endpoint or automatic login is manufactured.
"""
import socket
import threading

SERVER_SHUTDOWN = (18, b"\x10")


class Connections:
    """Track wrapped TLS peers, including clients not yet joined to World.

    Register after TLS setup using the normal framed send callback. Unregister
    in session finally. drain() first sends every notice, then half-closes every
    writable side. The owner must persist its normal disconnect/checkpoint
    state before process exit; this helper never mutates character storage.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._entries = {}
        self._stopping = False

    def register(self, peer, send):
        with self._lock:
            if self._stopping:
                return False
            self._entries[id(peer)] = (peer, send)
            return True

    def unregister(self, peer):
        with self._lock:
            self._entries.pop(id(peer), None)

    def drain(self):
        with self._lock:
            self._stopping = True
            entries = tuple(self._entries.values())
            self._entries.clear()
        results = []
        for peer, send in entries:
            error = None
            try:
                send(*SERVER_SHUTDOWN)
            except (OSError, ValueError) as failure:
                error = type(failure).__name__
            results.append({"peer": id(peer), "notice_error": error})
        # No lock is held while callbacks or sockets run. All notices precede
        # channel EOF, which is the native UI reset trigger.
        for peer, _ in entries:
            try:
                peer.shutdown(socket.SHUT_WR)
            except OSError:
                pass
        return tuple(results)
