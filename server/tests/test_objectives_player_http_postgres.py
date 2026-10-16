"""End-to-end player API auth, CORS and receipt scoping on isolated PostgreSQL."""
import http.server
import importlib.util
import json
from pathlib import Path
import threading
import urllib.error
import urllib.request
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.objectives import player_auth
from wakfu_server.custom_tasks import player_actions as world_actions

SERVICE_PATH = Path(__file__).resolve().parents[1] / "objectives-service" / "service.py"
SERVICE_SPEC = importlib.util.spec_from_file_location(
    "objectives_player_service_test", SERVICE_PATH
)
service = importlib.util.module_from_spec(SERVICE_SPEC)
SERVICE_SPEC.loader.exec_module(service)

HTTP_TRAVEL_ACTIONS = [
    {
        "action_key": "travel.test-map-1086",
        "label": "Visit the test destination",
        "target": {"map_id": 1086, "x": -11, "y": -17, "z": 0},
    }
]


class ObjectivesPlayerHttpPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("player-http-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "HTTP Main")["id"]
        self.other = self.store.create_character(self.account, "HTTP Other")["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character)
        self.connect_patch = patch.object(service, "connect", self.store.connection)
        self.connect_patch.start()
        self.addCleanup(self.connect_patch.stop)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        self.server.token = "private-evaluator-token-never-for-player"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def request(self, method, path, *, bearer=None, body=None, origin=None):
        headers = {}
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        if origin:
            headers["Origin"] = origin
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        request = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read()
            try:
                payload = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                payload = raw
            return response.code, payload, response.headers

    def _launch(self):
        with self.store.connection() as db:
            return player_auth.issue_launch(
                db, self.account, self.character, self.generation
            )

    def test_player_http_lifecycle_and_untrusted_origin_boundaries(self):
        code, config, headers = self.request(
            "GET", "/player-api/config", origin="http://localhost:18086"
        )
        self.assertEqual(code, 200)
        self.assertIn("http://localhost:18086", config["embed_origins"])
        self.assertEqual(
            headers.get("Access-Control-Allow-Origin"), "http://localhost:18086"
        )
        self.assertIn("Authorization", headers.get("Access-Control-Allow-Headers", ""))
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        self.assertEqual(headers.get("Referrer-Policy"), "no-referrer")
        csp = headers.get("Content-Security-Policy", "")
        self.assertIn("frame-ancestors", csp)
        self.assertNotIn("*", csp)
        preflight = self.request(
            "OPTIONS", "/player-api/actions", origin="http://localhost:18086"
        )
        self.assertEqual(preflight[0], 204)
        self.assertEqual(
            preflight[2].get("Access-Control-Allow-Origin"), "http://localhost:18086"
        )
        self.assertIn("POST", preflight[2].get("Access-Control-Allow-Methods", ""))

        denied = self.request(
            "GET", "/player-api/config", origin="https://attacker.invalid"
        )
        self.assertEqual(
            (denied[0], denied[1]), (403, {"error": "Embedding origin is not allowed"})
        )
        unauthenticated = self.request("GET", "/player-api/adventures")
        self.assertEqual(unauthenticated[0], 401)
        self.assertNotEqual(unauthenticated[0], 200)

        launch = self._launch()
        code, exchanged, _ = self.request(
            "POST", "/player-api/session", body={"token": launch}
        )
        self.assertEqual(code, 200)
        self.assertEqual(exchanged["character_id"], self.character)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT kind,expires_at FROM objectives_player_tokens WHERE digest=%s",
                (player_auth.digest(exchanged["token"]),),
            ).fetchone()
        self.assertEqual(row["kind"], "session")
        with self.store.connection() as db:
            seconds = db.execute(
                "SELECT extract(epoch FROM %s::timestamptz-CURRENT_TIMESTAMP) seconds",
                (row["expires_at"],),
            ).fetchone()["seconds"]
        self.assertGreater(seconds, 30 * 24 * 60 * 60 - 30)
        self.assertLessEqual(seconds, 30 * 24 * 60 * 60)
        repeated_code, repeated, _ = self.request(
            "POST", "/player-api/session", body={"token": launch}
        )
        self.assertEqual(repeated_code, 200)
        self.assertNotEqual(repeated["token"], exchanged["token"])
        self.assertEqual(repeated["expires_at"], exchanged["expires_at"])

        with patch("wakfu_server.objectives.player_travel.actions", return_value=[]):
            code, snapshot, player_headers = self.request(
                "GET", "/player-api/adventures", bearer=exchanged["token"]
            )
        self.assertEqual(code, 200, snapshot)
        self.assertEqual(snapshot["actor"]["id"], self.character)
        self.assertIn("sections", snapshot)
        self.assertNotIn("admin", json.dumps(snapshot).lower())
        self.assertEqual(player_headers.get("X-Content-Type-Options"), "nosniff")

        wrong_origin_action = self.request(
            "POST",
            "/player-api/actions",
            bearer=exchanged["token"],
            origin="https://attacker.invalid",
            body={"action_key": "travel.test-map-1086", "request_id": "http-1"},
        )
        self.assertEqual(wrong_origin_action[0], 403)
        forged_target = self.request(
            "POST",
            "/player-api/actions",
            bearer=exchanged["token"],
            body={
                "action_key": "travel.test-map-1086",
                "request_id": "http-forged",
                "target": {"map_id": 1, "x": 2, "y": 3, "z": 0},
            },
        )
        self.assertEqual(forged_target[0], 400)
        # The HTTP handler accepts a server-authored allowlisted travel key;
        # the browser never supplies a target or arbitrary coordinates.
        with patch(
            "wakfu_server.objectives.player_travel.actions",
            return_value=HTTP_TRAVEL_ACTIONS,
        ):
            code, receipt, _ = self.request(
                "POST",
                "/player-api/actions",
                bearer=exchanged["token"],
                body={"action_key": "travel.test-map-1086", "request_id": "http-1"},
            )
        self.assertEqual(code, 202)
        self.assertEqual(receipt["status"], "pending")
        self.assertNotIn("target", receipt)
        self.assertNotIn("generation", receipt)
        self.assertEqual(
            self.request(
                "GET", f"/player-api/actions/{receipt['id']}", bearer=exchanged["token"]
            )[0],
            200,
        )

        # The reusable token follows the account's newly selected character.
        self.store.select_character(self.account, self.generation, self.other)
        with patch(
            "wakfu_server.objectives.player_travel.actions",
            return_value=HTTP_TRAVEL_ACTIONS,
        ):
            selected_code, selected_view, _ = self.request(
                "GET", "/player-api/adventures", bearer=exchanged["token"]
            )
        self.assertEqual(selected_code, 200)
        self.assertEqual(selected_view["actor"]["id"], self.other)
        self.assertTrue(selected_view["connection"]["online"])
        self.assertTrue(selected_view["connection"]["actions_available"])
        # The same account UUID replays the original receipt even though World
        # now selects another owned character.
        replay_code, replay_receipt, _ = self.request(
            "POST",
            "/player-api/actions",
            bearer=exchanged["token"],
            body={"action_key": "travel.test-map-1086", "request_id": "http-1"},
        )
        self.assertEqual(replay_code, 202)
        self.assertEqual(replay_receipt["id"], receipt["id"])

        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE account_id=%s",
                (self.account,),
            )
        with patch("wakfu_server.objectives.player_travel.actions", return_value=[]):
            offline_code, offline_view, _ = self.request(
                "GET", "/player-api/adventures", bearer=exchanged["token"]
            )
        self.assertEqual(offline_code, 200)
        self.assertEqual(offline_view["actor"]["id"], self.character)
        self.assertFalse(offline_view["connection"]["online"])
        self.assertFalse(offline_view["connection"]["actions_available"])
        offline_action = self.request(
            "POST",
            "/player-api/actions",
            bearer=exchanged["token"],
            body={"action_key": "travel.test-map-1086", "request_id": "offline-action"},
        )
        self.assertEqual(offline_action[0], 409)

        new_generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, new_generation, self.character)
        with patch(
            "wakfu_server.objectives.player_travel.actions",
            return_value=HTTP_TRAVEL_ACTIONS,
        ):
            online_code, online_view, _ = self.request(
                "GET", "/player-api/adventures", bearer=exchanged["token"]
            )
        self.assertEqual(online_code, 200)
        self.assertTrue(online_view["connection"]["online"])
        self.assertTrue(online_view["connection"]["actions_available"])
        with patch(
            "wakfu_server.objectives.player_travel.actions",
            return_value=HTTP_TRAVEL_ACTIONS,
        ):
            action_code, current_action, _ = self.request(
                "POST",
                "/player-api/actions",
                bearer=exchanged["token"],
                body={
                    "action_key": "travel.test-map-1086",
                    "request_id": "current-action",
                },
            )
        self.assertEqual(action_code, 202)
        with self.store.connection() as db:
            identity = player_auth.authenticate(db, exchanged["token"])
            claimed = world_actions.claim(db, identity)
            self.assertEqual(claimed["generation"], new_generation)
            world_actions.lock_running(db, claimed)
            self.assertTrue(
                world_actions.finish(
                    db,
                    claimed,
                    {"success": True, "message": "executed under active lease"},
                )
            )
        receipt_code, saved_receipt, _ = self.request(
            "GET",
            f"/player-api/actions/{current_action['id']}",
            bearer=exchanged["token"],
        )
        self.assertEqual((receipt_code, saved_receipt["status"]), (200, "succeeded"))


if __name__ == "__main__":
    unittest.main()
