"""Real planner sessions cross both service boundaries with atomic attachments."""
import base64
from copy import deepcopy
import hashlib
from http.client import HTTPConnection
import json
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_query_search import fixture
from wakfu_ai.context.context_store import ContextStore
from wakfu_ai.http import server as http
from wakfu_ai.planning.query_sessions import QuerySessions
from wakfu_ai.transport.framed import FramedClient
from wakfu_ai.transport.framed_server import FramedServer


def attachment(value):
    body = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
    return dict(
        sha256=hashlib.sha256(body).hexdigest(),
        size=len(body),
        offset=0,
        data=base64.b64encode(body).decode(),
    )


class ContextBundleAcceptanceTests(unittest.TestCase):
    def exchange(self, protocol, *, reject_initial=False, reject_response=False):
        native = fixture([], edges=[])
        sessions = QuerySessions()
        with tempfile.TemporaryDirectory() as directory:
            store = ContextStore(directory)
            with patch.object(http, "context_store", return_value=store), patch.object(
                http, "_QUERY_SESSIONS", sessions
            ):
                server = (
                    http.BoundedHTTPServer(("127.0.0.1", 0), http.Handler)
                    if protocol == "http"
                    else FramedServer(("127.0.0.1", 0))
                )
                worker = threading.Thread(
                    target=server.serve_forever,
                    kwargs=dict(poll_interval=0.01),
                    daemon=True,
                )
                worker.start()
                client = (
                    FramedClient(*server.server_address) if protocol == "tcp" else None
                )

                def post(payload, endpoint="/v3/context/continue"):
                    if client is not None:
                        return client.request(endpoint, payload)
                    connection = HTTPConnection(*server.server_address, timeout=3)
                    try:
                        connection.request(
                            "POST",
                            endpoint,
                            json.dumps(payload),
                            {"Content-Type": "application/json"},
                        )
                        response = connection.getresponse()
                        return response.status, json.loads(response.read())
                    finally:
                        connection.close()

                try:
                    manifest = attachment(
                        dict(format="wakfu-complete-context-1", entries=[])
                    )
                    blocks = [
                        attachment(
                            native.store.objects[native.root_state["nativeContext"]]
                        ),
                        manifest,
                    ]
                    initial = deepcopy(native.envelope)
                    root = native.root_state["nativeContext"]
                    initial.update(
                        sourceKey="a" * 64,
                        catalogManifest=manifest["sha256"],
                        rootState=root,
                    )
                    initial["root"].update(key=root, nativeContext=root)
                    for block in blocks:
                        status, reply = post(block, "/v3/context/block")
                        self.assertEqual(status, 200, reply)
                    status, reply = post(initial, "/v3/decide")
                    self.assertEqual(status, 200, reply)
                    self.assertEqual(reply["status"], "query")
                    self.assertEqual(
                        post(deepcopy(initial), "/v3/decide"), (200, reply)
                    )
                    count = 0
                    while reply["status"] == "query":
                        query = reply["queries"][0]
                        answer = native.request(dict(query, state="root-state"))
                        response_blocks = [
                            attachment(value)
                            for value in native.store.objects.values()
                            if not store.has(attachment(value)["sha256"])
                        ]
                        request = dict(
                            requestId=initial["requestId"],
                            sourceKey=initial["sourceKey"],
                            response=answer,
                        )
                        continuation = dict(request=request, blocks=response_blocks)
                        if (reject_initial or reject_response) and count == 0:
                            invalid = deepcopy(continuation)
                            corrupt = attachment(dict(unpublished="sentinel"))
                            corrupt["data"] = base64.b64encode(b"wrong").decode()
                            invalid["blocks"].append(corrupt)
                            if reject_initial:
                                invalid["request"]["sourceKey"] = "f" * 64
                                invalid["blocks"].pop()
                            self.assertEqual(post(invalid)[0], 400)
                            self.assertEqual(post(initial, "/v3/decide"), (200, reply))
                            if not reject_initial:
                                self.assertTrue(
                                    all(
                                        not store.has(block["sha256"])
                                        for block in response_blocks
                                    )
                                )
                        continuation_endpoint = (
                            "/v3/context/continue" if response_blocks else "/v3/decide"
                        )
                        wire = continuation if response_blocks else request
                        status, reply = post(wire, continuation_endpoint)
                        self.assertEqual(status, 200, reply)
                        self.assertEqual(
                            post(deepcopy(wire), continuation_endpoint), (200, reply)
                        )
                        count += 1
                        self.assertLess(count, 12)
                    self.assertGreater(count, 0)
                    self.assertEqual(reply["decision"]["action"], dict(type="end_turn"))
                    self.assertEqual(
                        reply["decision"]["sourceKey"], initial["sourceKey"]
                    )
                    self.assertEqual(
                        reply["decision"]["requestId"], initial["requestId"]
                    )
                    self.assertEqual(len(sessions.sessions), 1)
                finally:
                    if client is not None:
                        client.close()
                    server.shutdown()
                    server.server_close()
                    worker.join(2)
                    store.close()

    def test_real_http_foreign_continuation_cannot_advance_existing_search(self):
        self.exchange("http", reject_initial=True)

    def test_real_tcp_foreign_continuation_cannot_advance_existing_search(self):
        self.exchange("tcp", reject_initial=True)

    def test_real_http_invalid_descendant_attachment_does_not_advance_search(self):
        self.exchange("http", reject_response=True)

    def test_real_tcp_invalid_descendant_attachment_does_not_advance_search(self):
        self.exchange("tcp", reject_response=True)
