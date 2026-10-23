"""Optional microservice channel preserves complete context and wire identity."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import socket
import struct
import tempfile
import threading
import time
import unittest
import urllib.error
from unittest.mock import patch

from wakfu_ai.bridge.world_bridge import ContextTransport
from wakfu_ai.context.context_store import ContextStore
from wakfu_ai.context.native_context import encode
from wakfu_ai.http import server as http
from wakfu_ai.native.native_deadline import bounded
from wakfu_ai.transport.framed import FramedClient, encode_frame, read_frame
from wakfu_ai.transport.framed_context import FramedContextTransport
from wakfu_ai.transport.framed_server import FramedServer, _processing_deadline


class FramedTransportTests(unittest.TestCase):
    def test_only_catalog_sealing_can_extend_processing_budget(self):
        channel = FramedClient("127.0.0.1", 1, timeout=120)
        self.assertEqual(channel.timeout, 120)
        with self.assertRaises(ValueError):
            FramedClient("127.0.0.1", 1, timeout=121)
        with patch(
            "wakfu_ai.transport.framed_server.time.monotonic", return_value=100
        ), patch("wakfu_ai.transport.framed_server.remaining", return_value=None):
            self.assertEqual(_processing_deadline("/v3/context/seal", 130), 220)
            for endpoint in (
                "/health",
                "/v3/decide",
                "/v3/context/continue",
                "/v3/context/block",
            ):
                self.assertEqual(_processing_deadline(endpoint, 130), 130)
        with patch(
            "wakfu_ai.transport.framed_server.time.monotonic", return_value=100
        ), patch("wakfu_ai.transport.framed_server.remaining", return_value=0.5):
            self.assertEqual(_processing_deadline("/v3/context/seal", 130), 100.5)
            self.assertEqual(_processing_deadline("/v3/decide", 130), 100.5)

    def test_catalog_seal_can_finish_after_normal_processing_limit(self):
        def slow(endpoint, payload):
            time.sleep(0.08)
            return 200, dict(complete=True)

        server = self.serve(dispatcher=slow, request_timeout=0.03)
        client = self.client(server, timeout=1)
        self.assertEqual(
            client.request("/v3/context/seal", {}), (200, dict(complete=True))
        )
        with self.assertRaises((ConnectionError, OSError)):
            client.request("/v3/context/status", {})

    def test_production_tcp_health_and_legacy_planners_use_same_channel(self):
        from test_tactical import snapshot
        from wakfu_ai.transport.health import health

        server = self.serve()
        info = health(*server.server_address)
        self.assertEqual(info["transport"], "tcp")
        self.assertEqual(info["protocols"], [1, 2, 3])
        self.assertEqual(info["capacity"]["decisions"], http.MAX_DECISIONS)
        client = self.client(server)
        first = snapshot()
        first["protocol"] = 1
        status, reply = client.request("/v1/decide", first)
        self.assertEqual(status, 200)
        self.assertEqual(reply, http.decide(first))
        second = snapshot()
        status, reply = client.request("/v2/decide", second)
        self.assertEqual(status, 200)
        expected = http.decide(second)
        for field in ("protocol", "requestId", "stateKey", "decision"):
            self.assertEqual(reply.get(field), expected.get(field))
        for wrong in (1, True, 3):
            self.assertEqual(
                client.request("/v2/decide", dict(second, protocol=wrong))[0], 400
            )
        self.assertEqual(client.tcp_opens, 1)

    def test_invalid_or_expired_deadlines_cannot_open_a_channel(self):
        client = FramedClient("127.0.0.1", 1)
        for deadline in (False, True, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                client.request("/v3/decide", {}, deadline=deadline)
        with self.assertRaises(TimeoutError):
            client.request("/v3/decide", {}, deadline=0)
        self.assertEqual(client.tcp_opens, 0)
        for timeout in (True, float("nan"), 0):
            with self.assertRaises(ValueError):
                FramedClient("127.0.0.1", 1, timeout=timeout)

    def serve(self, **kwargs):
        server = FramedServer(("127.0.0.1", 0), **kwargs)
        thread = threading.Thread(
            target=server.serve_forever, kwargs=dict(poll_interval=0.01), daemon=True
        )
        thread.start()
        self.addCleanup(thread.join, 1)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def client(self, server, **kwargs):
        client = FramedClient(*server.server_address, **kwargs)
        self.addCleanup(client.close)
        return client

    def test_persistent_frames_preserve_native_request_id_and_source(self):
        observed = []

        def dispatch(endpoint, payload):
            observed.append((endpoint, payload))
            return 200, payload

        client = self.client(self.serve(dispatcher=dispatch))
        for index in range(4):
            payload = dict(
                requestId="owner",
                sourceKey="a" * 64,
                response=dict(id=str(index), supported=True),
            )
            self.assertEqual(client.request("/v3/decide", payload), (200, payload))
        self.assertEqual(client.tcp_opens, 1)
        self.assertEqual(len(observed), 4)

    def test_complete_context_bytes_and_digests_match_http_transport(self):
        with tempfile.TemporaryDirectory() as root:
            store = ContextStore(root)
            self.addCleanup(store.close)
            with patch.object(http, "context_store", return_value=store):
                server = self.serve()
                transport = FramedContextTransport(*server.server_address)
                self.addCleanup(transport.close)
                value = dict(runtime=dict(future=[b"\x00\xff", list(range(500))]))
                graph = encode(value)
                digest = transport.instance(graph)
                # Identical superclass algorithm, with direct endpoint calls
                # isolating transport from checksum/compression behavior.
                baseline = ContextTransport("http://unused")
                baseline.request = lambda path, payload: http.context_request(
                    path, payload
                )
                self.assertEqual(digest, baseline.instance(graph))
                self.assertEqual(store.json(digest), graph)
                self.assertEqual(transport.instance(graph), digest)
                self.assertEqual(transport.metrics["tcpOpens"], 1)

    def test_fragmented_frame_and_back_to_back_frames(self):
        server = self.serve(dispatcher=lambda path, data: (200, data))
        with socket.create_connection(server.server_address) as peer:
            message = encode_frame(
                dict(id=1, endpoint="/v3/decide", payload=dict(value=1))
            )
            for byte in message:
                peer.sendall(bytes([byte]))
            answer = read_frame(peer, time.monotonic() + 1)
            self.assertEqual(answer["id"], 1)
            peer.sendall(
                b"".join(
                    encode_frame(
                        dict(id=i, endpoint="/v3/decide", payload=dict(value=i))
                    )
                    for i in (2, 3)
                )
            )
            self.assertEqual(read_frame(peer, time.monotonic() + 1)["id"], 2)
            self.assertEqual(read_frame(peer, time.monotonic() + 1)["id"], 3)

    def test_oversized_and_duplicate_id_frames_close_before_dispatch(self):
        calls = []
        server = self.serve(
            dispatcher=lambda path, data: (calls.append(data) or (200, data)),
            maximum=256,
        )
        with socket.create_connection(server.server_address) as peer:
            peer.settimeout(1)
            peer.sendall(struct.pack("!I", 257))
            self.assertEqual(peer.recv(1), b"")
        with socket.create_connection(server.server_address) as peer:
            peer.settimeout(1)
            frame = encode_frame(dict(id=1, endpoint="/v3/decide", payload={}))
            peer.sendall(frame)
            read_frame(peer, time.monotonic() + 1)
            peer.sendall(frame)
            self.assertEqual(peer.recv(1), b"")
        self.assertEqual(calls, [{}])

    def test_invalid_json_duplicate_keys_and_nonfinite_values_close(self):
        calls = []
        server = self.serve(
            dispatcher=lambda path, data: (calls.append(data) or (200, {}))
        )
        for body in (b'{"id":1,"id":2}', b'{"id":NaN}', b"not-json"):
            with socket.create_connection(server.server_address) as peer:
                peer.settimeout(1)
                peer.sendall(struct.pack("!I", len(body)) + body)
                self.assertEqual(peer.recv(1), b"")
        self.assertEqual(calls, [])

    def test_client_rejects_foreign_response_and_never_replays(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            calls = []

            def wrong():
                with listener.accept()[0] as peer:
                    calls.append(read_frame(peer, time.monotonic() + 1))
                    peer.sendall(encode_frame(dict(id=999, status=200, payload={})))

            thread = threading.Thread(target=wrong)
            thread.start()
            client = FramedClient(*listener.getsockname())
            with self.assertRaisesRegex(ValueError, "Foreign"):
                client.request("/v3/decide", {})
            thread.join(1)
            self.assertEqual(len(calls), 1)
            self.assertIsNone(client._peer)

    def test_absolute_deadline_and_reconnect_after_truncated_response(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()

            def drip():
                with listener.accept()[0] as peer:
                    read_frame(peer, time.monotonic() + 1)
                    peer.sendall(struct.pack("!I", 100))
                    for _ in range(20):
                        try:
                            peer.sendall(b" ")
                        except OSError:
                            break
                        time.sleep(0.02)

            thread = threading.Thread(target=drip)
            thread.start()
            client = FramedClient(*listener.getsockname(), timeout=1)
            started = time.monotonic()
            with self.assertRaises(TimeoutError):
                client.request("/v3/decide", {}, deadline=time.monotonic() + 0.08)
            self.assertLess(time.monotonic() - started, 0.35)
            self.assertIsNone(client._peer)
            thread.join(1)
        server = self.serve(dispatcher=lambda path, data: (200, data))
        client.address = server.server_address
        self.assertEqual(
            client.request("/v3/decide", dict(new=True)), (200, dict(new=True))
        )
        client.close()

    def test_owner_deadline_bounds_context_transport(self):
        server = self.serve(
            dispatcher=lambda path, data: (time.sleep(0.15) or (200, data))
        )
        transport = FramedContextTransport(*server.server_address)
        self.addCleanup(transport.close)
        with bounded(time.monotonic() + 0.03):
            with self.assertRaises(TimeoutError):
                transport.request("/v3/context/status", dict(objects=[]))

    def test_parallel_owner_channels_and_explicit_cancel_share_registry(self):
        started, cancelled = threading.Event(), threading.Event()

        class Sessions:
            def decide(self, payload, store):
                started.set()
                if not cancelled.wait(1):
                    raise TimeoutError()
                return dict(requestId=payload["requestId"], status="cancelled")

            def cancel(self, payload):
                cancelled.set()
                return dict(requestId=payload["requestId"], cancelled=True)

        with patch.object(http, "_QUERY_SESSIONS", Sessions()), patch.object(
            http, "context_store", return_value=object()
        ):
            server = self.serve()
            first, second = self.client(server), self.client(server)
            with ThreadPoolExecutor(max_workers=2) as pool:
                pending = pool.submit(
                    first.request,
                    "/v3/decide",
                    dict(requestId="owner", sourceKey="a" * 64),
                )
                self.assertTrue(started.wait(1))
                status, result = second.request(
                    "/v3/cancel", dict(requestId="owner", sourceKey="a" * 64)
                )
                self.assertEqual(status, 200)
                self.assertTrue(result["cancelled"])
                self.assertEqual(pending.result(1)[1]["requestId"], "owner")

    def test_connection_capacity_can_be_shared_with_http(self):
        capacity = threading.BoundedSemaphore(1)
        self.assertTrue(capacity.acquire(False))
        server = self.serve(connections=capacity)
        client = self.client(server)
        with self.assertRaises((ConnectionError, OSError)):
            client.request("/v3/cancel", {})
        capacity.release()
        with patch.object(http, "_QUERY_SESSIONS") as sessions:
            sessions.cancel.return_value = dict(cancelled=True)
            self.assertEqual(client.request("/v3/cancel", {})[0], 200)

    def test_server_error_preserves_status_and_channel_reuse(self):
        client = self.client(self.serve())
        self.assertEqual(client.request("/unknown", {})[0], 404)
        with patch.object(http, "context_store", side_effect=OSError("private")):
            self.assertEqual(
                client.request("/v3/context/status", dict(objects=[]))[0], 503
            )
        self.assertEqual(client.tcp_opens, 1)

    def test_context_error_closes_the_owner_channel(self):
        server = self.serve(dispatcher=lambda path, data: (503, dict(error="busy")))
        transport = FramedContextTransport(*server.server_address)
        self.addCleanup(transport.close)
        with self.assertRaises(urllib.error.HTTPError):
            transport.request("/v3/decide", {})
        self.assertIsNone(transport.channel._peer)

    def test_real_query_sessions_planner_negotiates_over_framed_channel(self):
        from copy import deepcopy
        from test_query_search import fixture, run_search
        from wakfu_ai.planning.query_sessions import QuerySessions

        native = fixture([], edges=[])
        expected = run_search(native)
        native = fixture([], edges=[])
        with tempfile.TemporaryDirectory() as root:
            store = ContextStore(root)
            self.addCleanup(store.close)
            sessions = QuerySessions()
            with patch.object(http, "context_store", return_value=store), patch.object(
                http, "_QUERY_SESSIONS", sessions
            ):
                server = self.serve()
                transport = FramedContextTransport(*server.server_address)
                self.addCleanup(transport.close)
                for digest, graph in native.store.objects.items():
                    raw = json.dumps(
                        graph, separators=(",", ":"), allow_nan=False
                    ).encode()
                    self.assertEqual(transport.bytes(raw), digest)
                manifest = transport.bytes(
                    json.dumps(
                        dict(format="wakfu-complete-context-1", entries=[]),
                        separators=(",", ":"),
                    ).encode()
                )
                root_key = native.root_state["nativeContext"]
                initial = deepcopy(native.envelope)
                initial.update(
                    sourceKey="a" * 64, catalogManifest=manifest, rootState=root_key
                )
                initial["root"].update(key=root_key, nativeContext=root_key)
                reply = transport.request("/v3/decide", initial)
                count = 0
                while reply["status"] == "query":
                    query = reply["queries"][0]
                    self.assertEqual(query["state"], root_key)
                    answer = native.request(dict(query, state="root-state"))
                    reply = transport.request(
                        "/v3/decide",
                        dict(
                            requestId=initial["requestId"],
                            sourceKey=initial["sourceKey"],
                            response=answer,
                        ),
                    )
                    count += 1
                self.assertGreater(count, 0)
                self.assertEqual(reply["decision"]["action"], expected["action"])
                self.assertEqual(reply["decision"]["requestId"], initial["requestId"])
                self.assertEqual(reply["decision"]["sourceKey"], initial["sourceKey"])
                self.assertEqual(transport.metrics["tcpOpens"], 1)


if __name__ == "__main__":
    unittest.main()
