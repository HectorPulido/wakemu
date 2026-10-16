"""Objectives admin proxy must retain the panel's session and CSRF boundary."""
import http.cookiejar
import json
import threading
import urllib.error
import urllib.request
import unittest
from types import SimpleNamespace
from unittest.mock import call, patch

from wakfu_server.admin_http import make_server


class ObjectivesAdminHttpTests(unittest.TestCase):
    def setUp(self):
        self.store = None
        self.server = make_server(
            SimpleNamespace(store=self.store),
            "127.0.0.1",
            0,
            credentials={
                "username": "operator",
                "password": "objectives-test-password",
            },
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
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
        req = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        try:
            response = self.client.open(req, timeout=5)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())
        with response:
            return response.code, json.loads(response.read())

    def login(self):
        status, payload = self.request(
            "POST",
            "/api/login",
            {
                "username": "operator",
                "password": "objectives-test-password",
            },
        )
        self.assertEqual(status, 200)
        self.csrf = payload["csrf_token"]

    def test_reads_require_admin_session_and_proxy_exact_resource(self):
        with patch(
            "wakfu_server.admin_objectives.request", return_value=(200, {"items": []})
        ) as upstream:
            self.assertEqual(self.request("GET", "/api/objectives/definitions")[0], 401)
            self.login()
            self.assertEqual(
                self.request("GET", "/api/objectives/definitions?limit=5")[0], 200
            )
            upstream.assert_called_once_with("GET", "/v1/definitions", "limit=5")

    def test_mutation_requires_session_and_csrf_and_attributes_operator(self):
        body = {"key": "daily-test", "enabled": True}
        route = "/api/objectives/definitions/daily-test"
        with patch(
            "wakfu_server.admin_objectives.request", return_value=(201, {"revision": 3})
        ) as upstream:
            self.assertEqual(self.request("PUT", route, body)[0], 401)
            self.login()
            self.assertEqual(self.request("PUT", route, body)[0], 403)
            self.assertEqual(self.request("PUT", route, body, csrf="wrong")[0], 403)
            self.assertEqual(
                self.request("PUT", route, body, csrf=self.csrf), (201, {"revision": 3})
            )
            upstream.assert_called_once_with(
                "PUT",
                "/v1/definitions/daily-test",
                payload={**body, "operator": "operator"},
            )

    def test_unknown_routes_fail_closed_and_upstream_errors_are_preserved(self):
        self.login()
        with patch(
            "wakfu_server.admin_objectives.request",
            return_value=(409, {"error": "revision conflict"}),
        ) as upstream:
            self.assertEqual(self.request("GET", "/api/objectives/unknown")[0], 405)
            self.assertEqual(
                self.request("POST", "/api/objectives/definitions/a", {}, self.csrf)[0],
                405,
            )
            self.assertEqual(
                self.request("PUT", "/api/objectives/definitions/a%2Fb", {}, self.csrf)[
                    0
                ],
                400,
            )
            self.assertEqual(
                self.request("PUT", "/api/objectives/definitions/a", {}, self.csrf),
                (409, {"error": "revision conflict"}),
            )
            self.assertEqual(upstream.call_count, 1)

    def test_quarantined_event_retry_requires_csrf_and_forwards_operator(self):
        route = "/api/objectives/events/55/retry"
        with patch(
            "wakfu_server.admin_objectives.request",
            return_value=(202, {"queued": True}),
        ) as upstream:
            self.assertEqual(self.request("POST", route, {})[0], 401)
            self.login()
            self.assertEqual(self.request("POST", route, {})[0], 403)
            self.assertEqual(
                self.request("POST", route, {}, self.csrf), (202, {"queued": True})
            )
            upstream.assert_called_once_with(
                "POST", "/v1/events/55/retry", payload={"operator": "operator"}
            )
            self.assertEqual(
                self.request("POST", "/api/objectives/events/0/retry", {}, self.csrf)[
                    0
                ],
                400,
            )

    def test_level_rewards_rankings_and_challenge_profiles_keep_session_and_csrf(self):
        self.login()
        with patch(
            "wakfu_server.admin_objectives.request", return_value=(200, {"items": []})
        ) as upstream:
            for resource in ("reward-policies", "rankings", "challenge-profiles"):
                self.assertEqual(
                    self.request("GET", f"/api/objectives/{resource}?limit=10")[0], 200
                )
            self.assertEqual(
                [call.args[:3] for call in upstream.call_args_list],
                [
                    ("GET", "/v1/reward-policies", "limit=10"),
                    ("GET", "/v1/rankings", "limit=10"),
                    ("GET", "/v1/challenge-profiles", "limit=10"),
                ],
            )

        for resource, key, body in (
            (
                "reward-policies",
                "level-reward-v1",
                {"policy": {"bands": []}, "expected_revision": 0},
            ),
            (
                "challenge-profiles",
                "challenge-v1",
                {"definition": {"enabled": True}, "expected_revision": 0},
            ),
        ):
            route = f"/api/objectives/{resource}/{key}"
            with self.subTest(route=route), patch(
                "wakfu_server.admin_objectives.request",
                return_value=(201, {"revision": 1}),
            ) as upstream:
                self.assertEqual(self.request("PUT", route, body)[0], 403)
                self.assertEqual(
                    self.request("PUT", route, body, self.csrf), (201, {"revision": 1})
                )
                upstream.assert_called_once_with(
                    "PUT",
                    f"/v1/{resource}/{key}",
                    payload={**body, "operator": "operator"},
                )

    def test_player_launch_requires_admin_session_csrf_and_valid_character_body(self):
        body = {"character_id": 73}
        expected = {
            "url": "https://game.example/player/#token=opaque-token",
            "valid_days": 30,
        }

        def issue(store, character_id):
            if type(character_id) is not int or character_id < 1:
                raise ValueError("Invalid character identifier")
            return expected

        with patch(
            "wakfu_server.admin_objectives.player_launch", side_effect=issue
        ) as launch:
            self.assertEqual(
                self.request("POST", "/api/objectives/player-launch", body)[0], 401
            )
            self.login()
            self.assertEqual(
                self.request("POST", "/api/objectives/player-launch", body)[0], 403
            )
            self.assertEqual(
                self.request(
                    "POST", "/api/objectives/player-launch", body, csrf="wrong"
                )[0],
                403,
            )
            self.assertEqual(
                self.request(
                    "POST",
                    "/api/objectives/player-launch",
                    {"character_id": True},
                    self.csrf,
                )[0],
                400,
            )
            self.assertEqual(
                self.request(
                    "POST",
                    "/api/objectives/player-launch",
                    {**body, "account_id": 2},
                    self.csrf,
                )[0],
                400,
            )
            self.assertEqual(
                self.request("POST", "/api/objectives/player-launch", body, self.csrf),
                (200, expected),
            )
            self.assertEqual(
                launch.call_args_list, [call(self.store, True), call(self.store, 73)]
            )


if __name__ == "__main__":
    unittest.main()
