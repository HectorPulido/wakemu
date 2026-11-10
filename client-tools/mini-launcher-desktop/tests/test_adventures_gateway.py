"""Exercise the public Adventures bridge over real loopback HTTP connections."""

import importlib.util
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import unittest
from urllib.parse import urlsplit
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "gateway/adventures_gateway.py"
spec = importlib.util.spec_from_file_location("launcher_adventures_gateway", SOURCE)
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


class UpstreamHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def route(self):
        size = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(size) if size else b""
        self.server.calls.append((self.command, self.path, dict(self.headers), body))
        status, response, headers = self.server.answer
        self.send_response(status)
        self.send_header("Content-Length", str(len(response)))
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response)

    do_GET = route
    do_POST = route


class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        cls.bridge = gateway.Server(("127.0.0.1", 0), gateway.Handler)
        cls.threads = []
        for server in (cls.upstream, cls.bridge):
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            cls.threads.append(worker)

    @classmethod
    def tearDownClass(cls):
        for server in (cls.bridge, cls.upstream):
            server.shutdown()
            server.server_close()
        for worker in cls.threads:
            worker.join(timeout=2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.secret = Path(self.temp.name) / "operator-token"
        self.secret.write_text("operator-only-fixture\n")
        self.patches = [
            patch.object(gateway, "UPSTREAM_HOST", "127.0.0.1"),
            patch.object(gateway, "UPSTREAM_PORT", self.upstream.server_port),
            patch.object(gateway, "TOKEN_FILE", str(self.secret)),
            patch.object(gateway, "LIMITS", gateway.LoginLimits()),
        ]
        for item in self.patches:
            item.start()
        self.upstream.calls = []
        self.upstream.answer = (
            200,
            b'{"token":"' + b"a" * 43 + b'"}',
            {"Content-Type": "application/json"},
        )

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def request(self, method, path, value=None, headers=None, raw=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.bridge.server_port, timeout=3
        )
        body = (
            raw
            if raw is not None
            else (json.dumps(value).encode() if value is not None else None)
        )
        request_headers = dict(headers or {})
        request_headers.setdefault("Host", urlsplit(gateway.PUBLIC_ORIGIN).netloc)
        if body is not None:
            request_headers.setdefault("Content-Type", "application/json")
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        connection.close()
        return result

    def login(self, **kwargs):
        return self.request(
            "POST",
            "/launcher/login",
            {"username": "fixture_user", "password": "fixture-password"},
            **kwargs
        )

    def test_auth_transport_errors_are_unavailable_and_bad_json_remains_invalid(self):
        headers = {"Host": urlsplit(gateway.UNIFIED_ORIGIN).netloc}
        credentials = {"username": "fixture_user", "password": "fixture-password"}
        for error in (
            ssl.SSLCertVerificationError(1, "expired-sensitive-fixture"),
            http.client.InvalidURL("upstream-sensitive-fixture"),
        ):
            with self.subTest(error=type(error).__name__), patch.object(
                gateway, "auth_upstream", side_effect=error
            ) as upstream:
                status, body, _ = self.request(
                    "POST", "/login", credentials, headers=headers
                )
                self.assertEqual(status, 503)
                self.assertEqual(
                    json.loads(body),
                    {"error": "Adventures is unavailable; try again shortly"},
                )
                self.assertNotIn(b"sensitive-fixture", body)
                upstream.assert_called_once()
        with patch.object(gateway, "auth_upstream") as upstream:
            status, body, _ = self.request("POST", "/login", raw=b"{", headers=headers)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body), {"error": "Invalid Adventures request"})
            upstream.assert_not_called()

    def test_unified_discovery_is_public_same_origin_and_unknown_hosts_are_rejected(
        self,
    ):
        host = urlsplit(gateway.UNIFIED_ORIGIN).netloc
        expected = dict(
            version=1,
            server_host=host,
            chat_host=host,
            dispatch_port=15558,
            game_ports=[15556],
            chat_port=16337,
            api_url=gateway.UNIFIED_ORIGIN,
            http_url=gateway.UNIFIED_ORIGIN,
            shop_url=gateway.UNIFIED_ORIGIN,
            achievements_url=gateway.UNIFIED_ORIGIN,
            certificate="",
        )
        for known in (host, host + ":443", urlsplit(gateway.PUBLIC_ORIGIN).netloc):
            status, body, headers = self.request(
                "GET", "/launcher/config", headers={"Host": known}
            )
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body), expected)
            self.assertNotIn("operator-only", body.decode())
            self.assertEqual(headers["Cache-Control"], "no-store")
        for foreign in (
            "foreign.example",
            host + ".foreign.example",
            "user@" + host,
            host + ":444",
        ):
            with self.subTest(host=foreign):
                self.assertEqual(
                    self.request("GET", "/launcher/config", headers={"Host": foreign})[
                        0
                    ],
                    421,
                )
        self.assertEqual(
            self.request("GET", "/health", headers={"Host": "127.0.0.1"})[0], 200
        )
        self.assertEqual(self.upstream.calls, [])

    def test_unified_login_link_is_scoped_to_requested_allowed_host(self):
        for origin in (gateway.PUBLIC_ORIGIN, gateway.UNIFIED_ORIGIN):
            with self.subTest(origin=origin):
                status, raw, _ = self.login(
                    headers={"Host": urlsplit(origin).netloc, "Origin": origin}
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    json.loads(raw)["url"], origin + "/player/#token=" + "a" * 43
                )

    def test_unified_auth_preserves_exact_credential_payload_and_limits_the_public_surface(
        self,
    ):
        public_headers = {
            "Host": urlsplit(gateway.UNIFIED_ORIGIN).netloc,
            "Origin": gateway.UNIFIED_ORIGIN,
            "Authorization": "Bearer client-fixture",
            "Cookie": "private=fixture",
            "X-Forwarded-For": "192.168.0.7",
        }
        raw = b'{"username":"fixture-user", "password":"fixture-password", "n":1.00}'
        response = b'{"fixture":"unchanged"}'
        for path in ("/login", "/register", "/remember", "/game-token"):
            with self.subTest(path=path), patch.object(
                gateway,
                "auth_upstream",
                return_value=(201, response, {"Content-Type": "application/json"}),
            ) as auth, patch.object(gateway, "shop_upstream") as shop:
                status, body, _ = self.request(
                    "POST", path, raw=raw, headers=public_headers
                )
                self.assertEqual((status, body), (201, response))
                method, sent_path, sent_raw, sent_headers = auth.call_args.args
                self.assertEqual((method, sent_path, sent_raw), ("POST", path, raw))
                self.assertEqual(sent_headers["Authorization"], "Bearer client-fixture")
                self.assertNotIn("Cookie", sent_headers)
                self.assertNotIn("X-Forwarded-For", sent_headers)
                self.assertNotIn("operator-only", str(sent_headers))
                shop.assert_not_called()
        for method, path in (
            ("POST", "/logout"),
            ("GET", "/characters"),
            ("GET", "/login"),
            ("POST", "/login?redirect=foreign"),
        ):
            with self.subTest(method=method, path=path), patch.object(
                gateway, "auth_upstream"
            ) as auth:
                self.assertEqual(
                    self.request(
                        method,
                        path,
                        raw=raw if method == "POST" else None,
                        headers=public_headers,
                    )[0],
                    404,
                )
                auth.assert_not_called()
        with patch.object(gateway, "auth_upstream") as auth:
            self.assertEqual(self.request("POST", "/login", raw=raw)[0], 404)
            rejected = dict(public_headers, Origin="https://foreign.example")
            self.assertEqual(
                self.request("POST", "/login", raw=raw, headers=rejected)[0], 403
            )
            auth.assert_not_called()
        self.assertEqual(self.upstream.calls, [])

    def test_unified_shop_preserves_queries_credentials_binary_and_exact_json_tokens(
        self,
    ):
        headers = {
            "Host": urlsplit(gateway.UNIFIED_ORIGIN).netloc,
            "Authorization": "Bearer shop-fixture",
            "APIKEY": "shop-key-fixture",
            "Cookie": "private=fixture",
        }
        old = "https://wakemu-shop.p.hectorpulido.net"
        raw = (
            '{"'
            + old
            + '":"unchanged-key", "url":"'
            + old
            + '/item-icons/2281.jpg", "n":1.00, "array":[true,null,1e+02]}'
        ).encode()
        expected = (
            '{"'
            + old
            + '":"unchanged-key", "url":"'
            + gateway.UNIFIED_ORIGIN
            + '/item-icons/2281.jpg", "n":1.00, "array":[true,null,1e+02]}'
        ).encode()
        paths = [
            ("GET", "/json/Ankama/v5/Account/GetAccessToken?apikey=fixture", None),
            ("POST", "/es/shops/WAKFU_INGAME/carts?lang=es", b'{"n":1.00}'),
        ]
        for method, path, request_body in paths:
            with self.subTest(path=path), patch.object(
                gateway,
                "shop_upstream",
                return_value=(200, raw, {"Content-Type": "application/json"}),
            ) as shop:
                status, body, _ = self.request(
                    method, path, raw=request_body, headers=headers
                )
                self.assertEqual((status, body), (200, expected))
                sent_method, sent_path, sent_body, sent_headers = shop.call_args.args
                self.assertEqual((sent_method, sent_path), (method, path))
                self.assertEqual(sent_body, request_body or b"")
                self.assertEqual(sent_headers["APIKEY"], "shop-key-fixture")
                self.assertEqual(sent_headers["Authorization"], "Bearer shop-fixture")
                self.assertEqual(sent_headers["Accept-Encoding"], "identity")
                self.assertNotIn("Cookie", sent_headers)
        binary = b"\xff\xd8fixture-jpeg\x00\xff\xd9"
        with patch.object(
            gateway,
            "shop_upstream",
            return_value=(200, binary, {"Content-Type": "image/jpeg"}),
        ):
            self.assertEqual(
                self.request("GET", "/item-icons/2281.jpg", headers=headers)[:2],
                (200, binary),
            )
        with patch.object(
            gateway,
            "shop_upstream",
            return_value=(
                200,
                b"fixture-encoded",
                {"Content-Type": "application/json", "Content-Encoding": "gzip"},
            ),
        ):
            self.assertEqual(
                self.request("GET", "/json/Ankama/test", headers=headers)[0], 503
            )
        with patch.object(gateway, "shop_upstream") as shop:
            self.assertEqual(self.request("GET", "/item-icons/2281.jpg")[0], 404)
            shop.assert_not_called()
        self.assertEqual(self.upstream.calls, [])

    def test_native_login_uses_server_secret_and_returns_only_public_scoped_url(self):
        status, raw, headers = self.login(
            headers={"Authorization": "Bearer attacker", "Cookie": "private=fixture"}
        )
        self.assertEqual(status, 200)
        value = json.loads(raw)
        self.assertEqual(
            value,
            {
                "url": gateway.PUBLIC_ORIGIN + "/player/#token=" + "a" * 43,
                "valid_days": 30,
            },
        )
        method, path, sent, body = self.upstream.calls.pop()
        self.assertEqual((method, path), ("POST", "/v1/player/gamedock-launch"))
        self.assertEqual(sent["Authorization"], "Bearer operator-only-fixture")
        self.assertNotIn("Cookie", sent)
        self.assertEqual(
            json.loads(body),
            {"username": "fixture_user", "password": "fixture-password"},
        )
        self.assertNotIn(b"operator-only", raw)
        self.assertNotIn(b"fixture-password", raw)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")

    def test_login_validation_origin_and_upstream_errors_do_not_leak_bodies(self):
        status, _, _ = self.login(headers={"Origin": "https://foreign.example"})
        self.assertEqual(status, 403)
        for request in (
            {"username": "fixture_user"},
            [],
            {"username": "fixture_user", "password": "short"},
            {"username": "bad user", "password": "fixture-password"},
            {
                "username": "fixture_user",
                "password": "fixture-password",
                "operator": "x",
            },
        ):
            with self.subTest(request=request):
                self.assertEqual(
                    self.request("POST", "/launcher/login", request)[0], 400
                )
        self.assertEqual(self.upstream.calls, [])
        for upstream_status, expected in ((401, 401), (400, 400), (500, 503)):
            self.upstream.answer = (upstream_status, b"upstream-sensitive-fixture", {})
            status, body, _ = self.login()
            self.assertEqual(status, expected)
            self.assertNotIn(b"upstream-sensitive", body)
        self.upstream.answer = (200, b'{"token":"not-valid"}', {})
        self.assertEqual(self.login()[0], 503)

    def test_player_assets_and_actions_preserve_payload_and_player_bearer_only(self):
        raw = b'{"fixture":"unchanged", "count":1.00}'
        self.upstream.answer = (
            202,
            raw,
            {
                "Content-Type": "application/json",
                "Content-Security-Policy": "default-src 'self'",
                "Set-Cookie": "upstream=secret",
                "Location": "http://private-host",
            },
        )
        fixtures = [
            ("GET", "/player/", None),
            ("GET", "/player/adventures.js", None),
            ("GET", "/player/adventures.css", None),
            ("GET", "/player/fonts/nunito.ttf", None),
            ("GET", "/player-api/config", None),
            ("GET", "/player-api/adventures", None),
            ("GET", "/player-api/actions/12345678-1234-1234-1234-123456789abc", None),
            ("POST", "/player-api/session", {"token": "fixture"}),
            (
                "POST",
                "/player-api/actions",
                {"action_key": "fixture-action", "request_id": "fixture-request"},
            ),
        ]
        for method, path, value in fixtures:
            with self.subTest(path=path):
                status, response, returned = self.request(
                    method,
                    path,
                    value,
                    headers={
                        "Authorization": "Bearer player-only-fixture",
                        "Origin": gateway.PUBLIC_ORIGIN,
                        "Cookie": "session=private",
                        "X-Forwarded-For": "192.168.0.7",
                    },
                )
                self.assertEqual((status, response), (202, raw))
                sent_method, sent_path, sent, body = self.upstream.calls[-1]
                self.assertEqual((sent_method, sent_path), (method, path))
                self.assertEqual(sent["Authorization"], "Bearer player-only-fixture")
                self.assertNotIn("operator-only-fixture", str(sent))
                for name in ("Origin", "Cookie", "X-Forwarded-For"):
                    self.assertNotIn(name, sent)
                self.assertNotIn("Set-Cookie", returned)
                self.assertNotIn("Location", returned)
                self.assertEqual(
                    returned["Content-Security-Policy"], "default-src 'self'"
                )
                if value is not None:
                    self.assertEqual(json.loads(body), value)

    def test_allowlist_excludes_operator_routes_query_strings_traversal_and_wrong_methods(
        self,
    ):
        fixtures = [
            ("GET", "/v1/player/gamedock-launch"),
            ("POST", "/v1/player/gamedock-launch"),
            ("GET", "/player/../operator"),
            ("GET", "/player/%2e%2e/operator"),
            ("GET", "/player-api/adventures?secret=value"),
            ("DELETE", "/player-api/actions"),
            ("POST", "/player-api/adventures"),
            ("GET", "/launcher/login"),
            ("GET", "/player/unknown.js"),
            ("GET", "/player-api/actions/not-a-uuid"),
            ("POST", "/player-api/config"),
            ("OPTIONS", "/player-api/session"),
        ]
        for method, path in fixtures:
            with self.subTest(method=method, path=path):
                self.assertEqual(
                    self.request(
                        method, path, {"ignored": "body"} if method == "POST" else None
                    )[0],
                    404,
                )
        self.assertEqual(self.upstream.calls, [])
        status, _, headers = self.request("GET", "/player")
        self.assertEqual((status, headers["Location"]), (308, "/player/"))

    def test_json_request_bounds_content_type_chunked_and_duplicate_lengths(self):
        fixtures = [
            (b"{", {}),
            (b"{}", {"Content-Type": "text/plain"}),
            (b"x" * (gateway.MAX_BODY + 1), {}),
            (b"{}", {"Transfer-Encoding": "chunked"}),
        ]
        for body, headers in fixtures:
            with self.subTest(headers=headers, size=len(body)):
                self.assertEqual(
                    self.request("POST", "/launcher/login", raw=body, headers=headers)[
                        0
                    ],
                    400,
                )
        # Duplicate lengths must be rejected before any body reaches the upstream.
        with socket.create_connection(
            ("127.0.0.1", self.bridge.server_port), timeout=3
        ) as connection:
            connection.sendall(
                (
                    "POST /launcher/login HTTP/1.1\r\nHost: "
                    + urlsplit(gateway.PUBLIC_ORIGIN).netloc
                    + "\r\nContent-Type: application/json\r\nContent-Length: 2\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}"
                ).encode()
            )
            self.assertIn(b" 400 ", connection.recv(4096).split(b"\r\n", 1)[0])
        self.assertEqual(self.upstream.calls, [])

    def test_login_limits_are_case_insensitive_bounded_and_expire(self):
        limits = gateway.LoginLimits()
        with patch.object(gateway.time, "monotonic", return_value=100):
            self.assertTrue(all(limits.admit("Alice") for _ in range(10)))
            self.assertFalse(limits.admit("ALICE"))
            for index in range(50):
                self.assertTrue(limits.admit("User" + str(index)))
            self.assertFalse(limits.admit("additional"))
        with patch.object(gateway.time, "monotonic", return_value=161):
            self.assertTrue(limits.admit("ALICE"))
        self.assertEqual(len(limits.global_hits), 1)
        gateway.LIMITS = gateway.LoginLimits()
        for _ in range(10):
            self.assertEqual(self.login()[0], 200)
        status, _, headers = self.login()
        self.assertEqual((status, headers["Retry-After"]), (429, "60"))
        self.assertEqual(len(self.upstream.calls), 10)

    def test_capacity_and_upstream_bounds_fail_closed(self):
        with patch.object(gateway, "CAPACITY", threading.BoundedSemaphore(0)):
            self.assertEqual(self.login()[0], 503)
        self.assertEqual(self.upstream.calls, [])
        self.upstream.answer = (200, b"x" * 65, {})
        with patch.object(gateway, "MAX_RESPONSE", 64):
            self.assertEqual(self.request("GET", "/player-api/adventures")[0], 503)
        self.secret.unlink()
        self.assertEqual(self.login()[0], 503)


if __name__ == "__main__":
    unittest.main(verbosity=2)
