"""GameDock bridge verifies native credentials without creating a World login."""
import http.server
import importlib.util
import json
from pathlib import Path
import threading
import urllib.error
import urllib.request
import unittest
from unittest.mock import MagicMock, patch

from postgres_case import PostgresCase
from wakfu_server.objectives import gamedock, player_auth


class ObjectivesGameDockPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("dock-owner", "dock-password-123")["id"]
        # Character appearance validation consults the native release catalogue;
        # the bridge behavior needs only isolated account/character rows.
        with patch("wakfu_server.breed_resources.playable_breeds", return_value=frozenset({15})):
            self.character = self.store.create_character(self.account, "Dock Main")["id"]
            self.alt = self.store.create_character(self.account, "Dock Alt")["id"]

    def test_bridge_issues_reusable_embed_without_mutating_world_login_state(self):
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, self.character)
        with self.store.connection() as db:
            before_sessions = db.execute(
                "SELECT account_id,character_id,generation,expires_at FROM sessions WHERE account_id=%s ORDER BY generation",
                (self.account,),
            ).fetchall()
            before_tokens = db.execute(
                "SELECT count(*) AS count FROM tokens WHERE account_id=%s",
                (self.account,),
            ).fetchone()["count"]

        result = gamedock.launch(
            self.store, {"username": "dock-owner", "password": "dock-password-123"}
        )
        self.assertEqual(result["valid_days"], 30)
        self.assertEqual(len(result["token"]), 43)

        # A GameDock embed can be opened while the native client is connected;
        # it must not replace the session or issue a native game token.
        with self.store.connection() as db:
            after_sessions = db.execute(
                "SELECT account_id,character_id,generation,expires_at FROM sessions WHERE account_id=%s ORDER BY generation",
                (self.account,),
            ).fetchall()
            after_tokens = db.execute(
                "SELECT count(*) AS count FROM tokens WHERE account_id=%s",
                (self.account,),
            ).fetchone()["count"]
            exchanged = player_auth.exchange_launch(db, result["token"])
            view_identity = player_auth.authenticate(db, exchanged["token"])
            embed_row = db.execute(
                "SELECT kind,account_id,character_id,generation,consumed_at "
                "FROM objectives_player_tokens WHERE digest=%s",
                (player_auth.digest(result["token"]),),
            ).fetchone()

        self.assertEqual(after_sessions, before_sessions)
        self.assertEqual(after_tokens, before_tokens)
        self.assertEqual(
            (embed_row["kind"], embed_row["account_id"], embed_row["character_id"], embed_row["generation"]),
            ("embed", self.account, self.character, ""),
        )
        self.assertIsNone(embed_row["consumed_at"])
        self.assertEqual(view_identity["account_id"], self.account)
        self.assertEqual(view_identity["character_id"], self.character)

    def test_credentials_are_exact_native_owner_and_never_accept_client_scope(self):
        other_account = self.store.register("dock-other", "other-password-123")["id"]
        self.assertIsNotNone(other_account)
        for credentials in (
            {"username": "dock-owner", "password": "wrong-password"},
            {"username": "dock-other", "password": "dock-password-123"},
        ):
            with self.subTest(credentials=credentials["username"]):
                with self.assertRaises(player_auth.Unauthorized):
                    gamedock.launch(self.store, credentials)
        for credentials in (
            {"username": "dock-owner", "password": "dock-password-123", "character_id": 1},
            {"username": "dock-owner", "password": "dock-password-123", "path": "/data/wakemu/account.json"},
            {"username": "../dock-owner", "password": "dock-password-123"},
        ):
            with self.subTest(extra=tuple(sorted(credentials))):
                with self.assertRaises(ValueError):
                    gamedock.launch(self.store, credentials)

        with self.store.connection() as db:
            issued = db.execute(
                "SELECT account_id,character_id FROM objectives_player_tokens WHERE kind='embed'"
            ).fetchall()
        self.assertEqual(issued, [])

    def test_existing_embed_identity_follows_selected_character_without_new_lease(self):
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, self.character)
        result = gamedock.launch(
            self.store, {"username": "dock-owner", "password": "dock-password-123"}
        )
        self.store.select_character(self.account, generation, self.alt)
        with self.store.connection() as db:
            session = player_auth.exchange_launch(db, result["token"])
            current = player_auth.authenticate(db, session["token"])
        self.assertEqual(current["account_id"], self.account)
        self.assertEqual(current["character_id"], self.alt)
        self.assertEqual(current["generation"], generation)


class GameDockLaunchServiceTests(unittest.TestCase):
    """The cross-service credential route is private to the service bearer."""

    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "objectives-service" / "service.py"
        spec = importlib.util.spec_from_file_location("gamedock_service_under_test", path)
        cls.service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.service)

    def setUp(self):
        self.server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), self.service.Handler
        )
        self.server.token = "private-objectives-test-token"
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1/player/gamedock-launch"

    def request(self, *, bearer=None, payload=None):
        data = json.dumps(payload).encode() if payload is not None else b"{}"
        headers = {"Content-Type": "application/json"}
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        request = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())
        with response:
            return response.status, json.loads(response.read())

    def test_missing_or_wrong_service_bearer_is_rejected_before_database_or_credentials(self):
        with patch.object(self.service, "connect", side_effect=AssertionError("DB reached")):
            for bearer in (None, "private-objectives-test-tokenx"):
                status, body = self.request(
                    bearer=bearer,
                    payload={"username": "sensitive-user", "password": "sensitive-password"},
                )
                self.assertEqual((status, body), (401, {"error": "Unauthorized"}))
                self.assertNotIn("sensitive-user", json.dumps(body))
                self.assertNotIn("sensitive-password", json.dumps(body))

    def test_valid_service_bearer_calls_only_the_native_bridge_and_returns_opaque_link(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        launch_result = {"token": "opaque-player-link", "valid_days": 30}
        with patch.object(self.service, "connect", return_value=connection), patch.object(
            self.service, "DATABASE_URL", "isolated-test-dsn"
        ):
            # The module is imported inside the handler, so patch its real import
            # target rather than attaching data to a live service connection.
            with patch(
                "wakfu_server.objectives.gamedock.launch", return_value=launch_result
            ) as launch, patch("wakfu_server.storage.store.Store") as store_class:
                status, body = self.request(
                    bearer="private-objectives-test-token",
                    payload={"username": "fixture-user", "password": "fixture-password"},
                )
        self.assertEqual((status, body), (200, launch_result))
        launch.assert_called_once()
        store_class.return_value.close.assert_called_once_with()
        self.assertNotIn("fixture-password", json.dumps(body))


if __name__ == "__main__":
    unittest.main()
