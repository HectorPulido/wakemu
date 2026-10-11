"""Native TLS/Spin listener with account-session-bound protobuf dispatch."""
import json
import logging
import socket
import socketserver
import struct
import threading

from wakfu_server import intergame_codec as codec


LOG = logging.getLogger(__name__)


class Connections:
    def __init__(self, domain):
        self.domain = domain
        self.lock = threading.RLock()
        self.peers = {}
        self.all_peers = set()
        self.closed = False

    def track(self, peer):
        with self.lock:
            if self.closed:
                peer.close()
                raise OSError("Intergame server is stopping")
            self.all_peers.add(peer)

    def close_all(self):
        with self.lock:
            self.closed = True
            peers = list(self.all_peers)
            self.peers.clear()
            self.all_peers.clear()
        for peer in peers:
            peer.close()

    def register(self, peer):
        with self.lock:
            if self.closed:
                raise OSError("Intergame server is stopping")
            previous = self.peers.get(peer.identity["account_id"])
            self.peers[peer.identity["account_id"]] = peer
        if previous is not None and previous is not peer:
            previous.close()

    def remove(self, peer):
        with self.lock:
            self.all_peers.discard(peer)
            if (
                peer.identity is not None
                and self.peers.get(peer.identity["account_id"]) is peer
            ):
                self.peers.pop(peer.identity["account_id"])

    def publish(self, events):
        for account, name, value in events:
            with self.lock:
                peer = self.peers.get(account)
            if peer is None:
                continue
            try:
                self.domain.active(peer.identity)
                peer.send(codec.event(name, value))
            except (OSError, ValueError, PermissionError):
                peer.close()


def make_server(domain, ssl_context, host="0.0.0.0", port=16337):
    connections = Connections(domain)

    class Handler(socketserver.BaseRequestHandler):
        def setup(self):
            self.identity = None
            self.send_lock = threading.Lock()
            self.request.settimeout(15)
            connections.track(self)
            try:
                self.request = ssl_context.wrap_socket(self.request, server_side=True)
            except Exception:
                connections.remove(self)
                raise
            self.request.settimeout(90)

        def close(self):
            try:
                self.request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.request.close()

        def send(self, data):
            with self.send_lock:
                self.request.sendall(codec.spin(0, data))

        def read_exact(self, size):
            result = bytearray()
            while len(result) < size:
                part = self.request.recv(size - len(result))
                if not part:
                    raise EOFError()
                result.extend(part)
            return bytes(result)

        def read_frame(self):
            size = struct.unpack(">I", self.read_exact(4))[0]
            if not 5 <= size <= codec.MAX_FRAME:
                raise ValueError("Invalid Spin frame size")
            body = self.read_exact(size - 4)
            if body[0] not in (0, 1, 2, 3) or (body[0] and len(body) != 1):
                raise ValueError("Invalid Spin control frame")
            return body[0], body[1:]

        def handle(self):
            try:
                kind, _ = self.read_frame()
                if kind != 1:
                    raise ValueError("Missing native availability request")
                self.request.sendall(codec.spin(2))
                kind, body = self.read_frame()
                if kind != 0 or len(body) > 8192:
                    raise ValueError("Invalid intergame authentication frame")
                auth = json.loads(body)
                if type(auth) is not dict or auth.get("clientType") != 2:
                    raise ValueError("Invalid intergame authentication")
                try:
                    self.identity = domain.authenticate(auth.get("token"))
                except (PermissionError, ValueError):
                    self.send(b'{"success":false,"errCode":1}')
                    return
                self.send(b'{"success":true,"errCode":0}')
                connections.register(self)
                while True:
                    kind, body = self.read_frame()
                    if kind == 3:
                        domain.active(self.identity)
                        continue
                    if kind != 0:
                        raise ValueError("Unexpected Spin control after authentication")
                    self.dispatch(body)
            except (EOFError, OSError, ValueError, PermissionError):
                pass
            except Exception:
                LOG.exception("Intergame connection failed")
            finally:
                connections.remove(self)

        def dispatch(self, body):
            frame = codec.decode("transport.Frame", body)
            if "request" not in frame:
                raise ValueError("Expected native intergame request")
            request = frame["request"]
            correlation = request.get("correlation_id", 0)
            payload = request.get("payload", {})
            name = codec.NAMES.get(payload.get("id", 0))
            try:
                if name is None:
                    raise ValueError("Unknown native intergame message")
                value = codec.decode(name, payload.get("data", b""))
                response_name, response_value, events = domain.handle(
                    self.identity, name, value
                )
            except PermissionError:
                self.send(codec.response(correlation, status=2))
                return
            except (ValueError, KeyError, TypeError):
                self.send(codec.response(correlation, status=3))
                return
            self.send(
                codec.response(correlation, name=response_name, value=response_value)
            )
            connections.publish(events)

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    result = Server((host, port), Handler)
    result.connections = connections
    result.close_peers = connections.close_all
    return result
