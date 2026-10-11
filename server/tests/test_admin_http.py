"""HTTP security contracts for the operator panel, using no database."""
import http.cookiejar
import http.client
import json
import threading
import urllib.error
from urllib.parse import quote
import urllib.request
import unittest
from pathlib import Path
from unittest.mock import patch

from wakfu_server.admin_http import make_server


class FakeAdminService:
    def __init__(self):
        self.calls = []

    @staticmethod
    def page(limit, offset):
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid pagination")

    def accounts(self, **options):
        return {"items": [], "total": 0}

    def dashboard(self):
        return {"counts": {"accounts": 1}, "online": []}

    def ban_account(self, account_id, data, operator):
        self.calls.append(("ban", account_id, data, operator))
        return {"id": account_id, "banned": True}

    def unban_account(self, account_id, data, operator):
        self.calls.append(("unban", account_id, data, operator))
        return {"id": account_id, "banned": False}

    def create_account(self, data, operator):
        return {"username": data["username"], "operator": operator}

    def characters(self, **options):
        return {"items": [], "total": 0, **options}

    def character(self, character_id):
        self.calls.append(("character", character_id))
        return {"id": character_id, "online": True}

    def grant_item(self, character_id, data, operator):
        self.calls.append(("grant_item", character_id, data, operator))
        return {"handle": "grant-1", "status": "pending"}

    def teleport_character(self, character_id, data, operator):
        self.calls.append(("teleport", character_id, data, operator))
        return {"handle": "teleport-1", "status": "pending"}

    def action(self, handle):
        self.calls.append(("action", handle))
        return {"handle": handle, "status": "failed", "error": "Inventory is full"}

    def profiler(self):
        return {
            "available": False,
            "status": None,
            "report": None,
            "error": "Profiler unavailable",
        }

    def settings(self, **options):
        return {"items": [], "total": 0, **options}

    def setting(self, name):
        self.calls.append(("setting", name))
        return {"name": name, "value": {"enabled": True}}

    def update_setting(self, name, data, operator):
        self.calls.append(("update_setting", name, data, operator))
        return {"name": name, "changed_name": name, "apply_mode": "new_actions"}

    def operation_services(self):
        return {"items": [{"name": "world", "available": True, "restartable": True}]}

    def restart_service(self, data, operator):
        self.calls.append(("restart_service", data, operator))
        return {"handle": "restart-1", "status": "pending"}

    def operation(self, handle):
        self.calls.append(("operation", handle))
        return {"handle": handle, "status": "completed"}


class AdminHttpTests(unittest.TestCase):
    def setUp(self):
        static = Path(__file__).resolve().parents[1] / "admin-service" / "static"
        self.service = FakeAdminService()
        self.server = make_server(
            self.service,
            "127.0.0.1",
            0,
            credentials={"username": "operator", "password": "operator-test-password"},
            static_dir=static,
        )
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = "http://127.0.0.1:%s" % self.server.server_port
        self.cookies = http.cookiejar.CookieJar()
        self.client = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
        )
        self.csrf = None

    def request(self, method, path, body=None, csrf=None):
        headers = {}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        if csrf is not None:
            headers["X-CSRF-Token"] = csrf
        request = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        try:
            response = self.client.open(request, timeout=5)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read()), error.headers
        with response:
            payload = (
                json.loads(response.read())
                if response.headers.get_content_type() == "application/json"
                else response.read()
            )
            return response.code, payload, response.headers

    def login(self):
        status, payload, headers = self.request(
            "POST",
            "/api/login",
            {"username": "operator", "password": "operator-test-password"},
        )
        self.assertEqual(200, status)
        self.csrf = payload["csrf_token"]
        cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        return payload

    def test_account_ban_routes_require_session_and_csrf_and_record_operator(self):
        for action in ("ban", "unban"):
            status, _, _ = self.request(
                "POST", "/api/accounts/42/" + action, {"reason": "Fixture"}
            )
            self.assertEqual(status, 401)
        self.login()
        for action in ("ban", "unban"):
            path = "/api/accounts/42/" + action
            status, _, _ = self.request("POST", path, {"reason": "Fixture"})
            self.assertEqual(status, 403)
            status, payload, _ = self.request(
                "POST", path, {"reason": "Fixture"}, csrf=self.csrf
            )
            self.assertEqual(status, 200)
            self.assertEqual(payload["banned"], action == "ban")
            self.assertEqual(
                self.service.calls[-1], (action, 42, {"reason": "Fixture"}, "operator")
            )

    def test_api_requires_session_and_mutations_require_csrf_then_allow_logout(self):
        status, _payload, _headers = self.request("GET", "/api/accounts")
        self.assertEqual(401, status)

        self.login()
        status, _payload, _headers = self.request(
            "POST",
            "/api/accounts",
            {"username": "fixture-user"},
        )
        self.assertEqual(403, status)
        status, result, _headers = self.request(
            "POST",
            "/api/accounts",
            {"username": "fixture-user"},
            self.csrf,
        )
        self.assertEqual(200, status)
        self.assertEqual({"username": "fixture-user", "operator": "operator"}, result)

        status, _payload, headers = self.request("POST", "/api/logout", {}, self.csrf)
        self.assertEqual(200, status)
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        status, _payload, _headers = self.request("GET", "/api/accounts")
        self.assertEqual(401, status)

    def test_login_failure_and_public_static_security_headers(self):
        status, _payload, _headers = self.request(
            "POST",
            "/api/login",
            {"username": "operator", "password": "wrong-password"},
        )
        self.assertEqual(401, status)
        status, _payload, headers = self.request("GET", "/")
        self.assertEqual(200, status)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual("DENY", headers["X-Frame-Options"])
        status, _payload, _headers = self.request(
            "GET", "/static/../../../../etc/passwd"
        )
        self.assertEqual(404, status)

    def test_invalid_pagination_is_rejected_before_domain_query(self):
        self.login()
        status, _payload, _headers = self.request("GET", "/api/accounts?limit=10000")
        self.assertEqual(400, status)

    def test_dashboard_normalizes_world_and_shop_health_contracts(self):
        class Response:
            def __init__(self, payload):
                self.payload = json.dumps(payload).encode()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return self.payload

        self.login()
        with patch(
            "wakfu_server.admin_http.urlopen",
            side_effect=[
                Response({"ok": True, "service": "world"}),
                Response({"status": "ok"}),
            ],
        ):
            status, payload, _headers = self.request("GET", "/api/dashboard")
        self.assertEqual(200, status)
        self.assertTrue(payload["services"]["world"]["ok"])
        self.assertTrue(payload["services"]["shop"]["ok"])

    def test_character_actions_require_csrf_and_return_receipts_without_claiming_completion(
        self,
    ):
        self.login()
        for route, body in (
            (
                "/api/characters/42/items",
                {"item_ref": 2021, "quantity": 1, "request_id": "grant-42"},
            ),
            (
                "/api/characters/42/teleport",
                {"map_id": 9, "x": 3, "y": 4, "z": 0, "request_id": "tp-42"},
            ),
        ):
            with self.subTest(route=route):
                status, _payload, _headers = self.request("POST", route, body)
                self.assertEqual(403, status)
                self.assertEqual([], self.service.calls)
                status, receipt, _headers = self.request("POST", route, body, self.csrf)
                self.assertEqual(200, status)
                self.assertEqual("pending", receipt["status"])
                expected_call = "grant_item" if route.endswith("/items") else "teleport"
                self.assertEqual(
                    [expected_call], [call[0] for call in self.service.calls]
                )
                self.service.calls.clear()

    def test_action_poll_preserves_failure_receipt_instead_of_rewriting_as_success(
        self,
    ):
        self.login()
        status, receipt, _headers = self.request("GET", "/api/actions/grant-1")
        self.assertEqual(200, status)
        self.assertEqual("failed", receipt["status"])
        self.assertIn("error", receipt)
        self.assertEqual(("action", "grant-1"), self.service.calls[-1])

    def test_profiler_route_returns_unavailable_data_without_failing_the_panel(self):
        self.login()
        status, payload, _headers = self.request("GET", "/api/profiler")
        self.assertEqual(200, status)
        self.assertFalse(payload["available"])
        self.assertIsNone(payload["report"])
        self.assertIn("unavailable", payload["error"].lower())

    def test_settings_route_unquotes_names_and_large_patch_requires_csrf(self):
        self.login()
        status, value, _headers = self.request(
            "GET", "/api/settings/monster_reproduction"
        )
        self.assertEqual(200, status)
        self.assertEqual("monster_reproduction", value["name"])
        self.assertEqual(("setting", "monster_reproduction"), self.service.calls[-1])
        encoded_name = "dungeon_runtime_config:rift:v1"
        status, value, _headers = self.request(
            "GET", "/api/settings/" + quote(encoded_name, safe="")
        )
        self.assertEqual(200, status)
        self.assertEqual(encoded_name, value["name"])
        self.assertEqual(("setting", encoded_name), self.service.calls[-1])

        body = {"value": {"notes": "x" * 40000}, "expected_revision": "a" * 32}
        status, _payload, _headers = self.request(
            "PATCH", "/api/settings/monster_reproduction", body
        )
        self.assertEqual(403, status)
        self.assertEqual("setting", self.service.calls[-1][0])
        status, result, _headers = self.request(
            "PATCH",
            "/api/settings/monster_reproduction",
            body,
            self.csrf,
        )
        self.assertEqual(200, status)
        self.assertEqual("monster_reproduction", result["changed_name"])
        self.assertEqual(40000, len(self.service.calls[-1][2]["value"]["notes"]))

        calls_before = len(self.service.calls)
        cookie = next(
            item.value for item in self.cookies if item.name == "wakemu_admin"
        )
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=5
        )
        connection.request(
            "PATCH",
            "/api/settings/monster_reproduction",
            body=b"",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(8 * 1024 * 1024 + 1),
                "Cookie": "wakemu_admin=" + cookie,
                "X-CSRF-Token": self.csrf,
            },
        )
        response = connection.getresponse()
        status = response.status
        response.read()
        connection.close()
        self.assertEqual(400, status)
        self.assertEqual(calls_before, len(self.service.calls))

    def test_service_restart_routes_require_csrf_and_expose_receipts(self):
        self.login()
        status, services, _headers = self.request("GET", "/api/operations/services")
        self.assertEqual(200, status)
        self.assertEqual("world", services["items"][0]["name"])
        body = {"service": "world", "request_id": "restart-ui-1"}
        status, _payload, _headers = self.request(
            "POST", "/api/operations/restart", body
        )
        self.assertEqual(403, status)
        status, receipt, _headers = self.request(
            "POST",
            "/api/operations/restart",
            body,
            self.csrf,
        )
        self.assertEqual(200, status)
        self.assertEqual("pending", receipt["status"])
        status, receipt, _headers = self.request("GET", "/api/operations/restart-1")
        self.assertEqual(200, status)
        self.assertEqual("completed", receipt["status"])


if __name__ == "__main__":
    unittest.main()
