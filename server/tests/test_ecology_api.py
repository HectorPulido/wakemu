"""Exercise the internal ecology API through an ephemeral real HTTP server."""

import json
import threading
import unittest
import urllib.error
import urllib.request
from types import SimpleNamespace

from wakfu_server.api import serve_api
from wakfu_server.ecology.protocol import MAX_BODY_BYTES, proposal
from wakfu_server.ecology.world_bridge import EcologyWorldBridge


class EcologyApiTests(unittest.TestCase):
    def setUp(self):
        self.players = []
        self.bridge = EcologyWorldBridge(
            store=object(),
            world=SimpleNamespace(ecology_snapshot=lambda: self.players),
            groups=SimpleNamespace(),
            harvests=SimpleNamespace(lock=threading.RLock(), targets={}),
            plantings=SimpleNamespace(
                growth_seconds=30, open_test_policy=False, ecology_world_epoch=None
            ),
            token="external-ecology-secret",
            mode="external",
        )
        self.ready = threading.Event()
        servers = []

        def on_ready(server):
            servers.append(server)
            self.ready.set()

        self.thread = threading.Thread(
            target=serve_api,
            args=(object(), "127.0.0.1", 0),
            kwargs={"ecology_bridge": self.bridge, "on_ready": on_ready},
            daemon=True,
        )
        self.thread.start()
        self.assertTrue(self.ready.wait(2), "API server did not become ready")
        self.server = servers[0]
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(
        self,
        method,
        path,
        *,
        body=None,
        raw=None,
        token="external-ecology-secret",
        authorization=None,
        headers=None,
    ):
        request_headers = {}
        if authorization is not None:
            request_headers["Authorization"] = authorization
        elif token is not None:
            request_headers["Authorization"] = "Bearer " + token
        if body is not None:
            request_headers["Content-Type"] = "application/json"
            raw = json.dumps(body).encode()
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            self.base + path,
            data=raw if method == "POST" else None,
            headers=request_headers,
            method=method,
        )
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as response:
            return response.code, json.load(response)
        with response:
            return response.status, json.load(response)

    def test_snapshot_requires_exact_bearer_and_returns_only_authorized_route(self):
        for header in (
            None,
            "external-ecology-secret",
            "bearer external-ecology-secret",
            "Bearer wrong",
        ):
            with self.subTest(header=header):
                self.assertEqual(
                    self.request(
                        "GET",
                        "/internal/ecology/snapshot",
                        token=None,
                        authorization=header,
                    )[0],
                    401,
                )
        status, snapshot = self.request("GET", "/internal/ecology/snapshot")
        self.assertEqual(status, 200)
        self.assertEqual(snapshot["world_epoch"], self.bridge.epoch)
        self.assertEqual(snapshot["players"], [])
        self.assertEqual(
            self.request(
                "GET",
                "/internal/ecology/snapshot/",
            )[0],
            404,
        )
        self.assertEqual(
            self.request("POST", "/internal/ecology/snapshot", body={})[0], 404
        )

    def test_apply_validates_json_schema_and_returns_domain_results(self):
        envelope = {"schema_version": 1, "proposals": []}
        self.assertEqual(
            self.request("POST", "/internal/ecology/apply", body=envelope),
            (200, {"schema_version": 1, "results": []}),
        )
        for raw in (b"not-json", b"[]", b'{"schema_version":1,"proposals":[{}]}'):
            with self.subTest(raw=raw):
                self.assertEqual(
                    self.request("POST", "/internal/ecology/apply", raw=raw)[0],
                    400,
                )
        self.assertEqual(
            self.request("POST", "/internal/ecology/apply/extra", body=envelope)[0],
            404,
        )

    def test_apply_rejects_missing_or_oversized_content_length_before_read(self):
        self.assertEqual(
            self.request("POST", "/internal/ecology/apply", raw=b"")[0], 413
        )
        self.assertEqual(
            self.request(
                "POST",
                "/internal/ecology/apply",
                raw=b"",
                headers={"Content-Length": str(MAX_BODY_BYTES + 1)},
            )[0],
            413,
        )

    def test_busy_bridge_maps_to_service_unavailable_and_recovers(self):
        self.assertTrue(self.bridge.gate.acquire(blocking=False))
        try:
            status, body = self.request(
                "POST",
                "/internal/ecology/apply",
                body={"schema_version": 1, "proposals": []},
            )
        finally:
            self.bridge.gate.release()
        self.assertEqual((status, body), (503, {"error": "Ecology bridge is busy"}))
        self.assertEqual(
            self.request(
                "POST",
                "/internal/ecology/apply",
                body={"schema_version": 1, "proposals": []},
            )[0],
            200,
        )

    def test_disabled_bridge_and_unauthorized_route_fail_closed(self):
        self.bridge.mode = "disabled"
        calls = []
        self.bridge.handlers["plants"] = lambda payload: calls.append(payload) or {
            "status": "applied"
        }
        row = proposal("plants", {"world_epoch": self.bridge.epoch}, self.bridge.epoch)
        status, body = self.request(
            "POST",
            "/internal/ecology/apply",
            body={"schema_version": 1, "proposals": [row]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["results"], [{"id": row["id"], "status": "stale"}])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
