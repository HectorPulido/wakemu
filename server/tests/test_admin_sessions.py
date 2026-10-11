"""Persistent administrator-session HTTP contracts backed by isolated PostgreSQL."""
import hashlib
import http.cookiejar
import json
from pathlib import Path
import threading
import urllib.error
import urllib.request

from postgres_case import PostgresCase
from wakfu_server.admin_http import make_server


class SessionAdminService:
    def __init__(self, store):
        self.store = store
        self.created = []

    @staticmethod
    def page(limit, offset):
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid pagination")

    def create_account(self, data, operator):
        self.created.append((data, operator))
        return {"username": data["username"], "operator": operator}


class AdminSessionsPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.service = SessionAdminService(self.store)
        self.credentials = {
            "username": "session-operator",
            "password": "session-test-password",
        }
        self.static = Path(__file__).resolve().parents[1] / "admin-service" / "static"
        self.servers = []

    def _server(self, credentials=None):
        server = make_server(
            self.service,
            "127.0.0.1",
            0,
            credentials=credentials or self.credentials,
            static_dir=self.static,
        )
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.servers.append(server)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return "http://127.0.0.1:%s" % server.server_port

    @staticmethod
    def _client():
        cookies = http.cookiejar.CookieJar()
        return (
            urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies)),
            cookies,
        )

    @staticmethod
    def _request(client, base, method, path, body=None, csrf=None):
        headers = {}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        if csrf is not None:
            headers["X-CSRF-Token"] = csrf
        request = urllib.request.Request(
            base + path, data=data, headers=headers, method=method
        )
        try:
            response = client.open(request, timeout=5)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read()), error.headers
        with response:
            return response.code, json.loads(response.read()), response.headers

    def _login(self, client, cookies, base):
        status, payload, _headers = self._request(
            client,
            base,
            "POST",
            "/api/login",
            {
                "username": self.credentials["username"],
                "password": self.credentials["password"],
            },
        )
        self.assertEqual(status, 200)
        token = next(
            cookie.value for cookie in cookies if cookie.name == "wakemu_admin"
        )
        return token, payload["csrf_token"]

    def test_cookie_and_csrf_survive_admin_http_server_recreation_then_logout_revokes(
        self,
    ):
        client, _cookies = self._client()
        first = self._server()
        token, csrf = self._login(client, _cookies, first)

        second = self._server()
        status, session, _headers = self._request(client, second, "GET", "/api/session")
        self.assertEqual(status, 200)
        self.assertEqual(session["username"], self.credentials["username"])
        self.assertEqual(session["csrf_token"], csrf)

        status, _payload, _headers = self._request(
            client, second, "POST", "/api/accounts", {"username": "fixture"}
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.service.created, [])
        status, created, _headers = self._request(
            client, second, "POST", "/api/accounts", {"username": "fixture"}, csrf
        )
        self.assertEqual(status, 200)
        self.assertEqual(created["operator"], self.credentials["username"])
        self.assertEqual(len(self.service.created), 1)

        status, _payload, headers = self._request(
            client, second, "POST", "/api/logout", {}, csrf
        )
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        status, _payload, _headers = self._request(
            client, second, "GET", "/api/session"
        )
        self.assertEqual(status, 401)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) n FROM admin_panel_sessions").fetchone()[
                    "n"
                ],
                0,
            )

    def test_only_sha256_token_is_persisted_in_session_row(self):
        client, _cookies = self._client()
        base = self._server()
        token, _csrf = self._login(client, _cookies, base)
        digest = hashlib.sha256(token.encode()).hexdigest()

        with self.store.connection() as db:
            rows = db.execute("SELECT * FROM admin_panel_sessions").fetchall()
        self.assertEqual(len(rows), 1)
        values = [
            value.decode() if isinstance(value, bytes) else str(value)
            for value in rows[0].values()
        ]
        self.assertIn(digest, values)
        self.assertNotIn(token, values)

    def test_expired_and_old_credential_revision_sessions_are_rejected(self):
        client, _cookies = self._client()
        original_server = self._server()
        _token, _csrf = self._login(client, _cookies, original_server)
        with self.store.connection() as db:
            db.execute(
                "UPDATE admin_panel_sessions SET expires_at=now()-interval '1 second'"
            )
        status, _payload, _headers = self._request(
            client, original_server, "GET", "/api/session"
        )
        self.assertEqual(status, 401)

        changed_client, _changed_cookies = self._client()
        old_server = self._server()
        old_token, _old_csrf = self._login(changed_client, _changed_cookies, old_server)
        changed_credentials = dict(
            self.credentials, password="replacement-test-password"
        )
        replacement_server = self._server(changed_credentials)
        status, _payload, _headers = self._request(
            changed_client, replacement_server, "GET", "/api/session"
        )
        self.assertEqual(status, 401)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT credential_revision FROM admin_panel_sessions WHERE token_sha256=%s",
                (hashlib.sha256(old_token.encode()).hexdigest(),),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertNotEqual(
            row["credential_revision"],
            hashlib.sha256(
                (
                    changed_credentials["username"]
                    + "\0"
                    + changed_credentials["password"]
                ).encode()
            ).hexdigest(),
        )
        self.assertEqual(
            row["credential_revision"],
            hashlib.sha256(
                (
                    self.credentials["username"] + "\0" + self.credentials["password"]
                ).encode()
            ).hexdigest(),
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
