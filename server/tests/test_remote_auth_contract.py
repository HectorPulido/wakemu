"""Real API and Store contracts in a UUID schema; never the runtime database."""
import json
import threading
import urllib.error
import urllib.request
from postgres_case import PostgresCase
from wakfu_server.api import serve_api


class RemoteAuthContractTests(PostgresCase):
    def test_login_remember_and_bridge_game_token_contract(self):
        fixture = self.store.register("remoteauthfixture", "fixture-password-only")
        ready = threading.Event()
        servers = []

        def on_ready(server):
            servers.append(server)
            ready.set()

        worker = threading.Thread(
            target=serve_api,
            args=(self.store, "127.0.0.1", 0),
            kwargs={"on_ready": on_ready},
            daemon=True,
        )
        worker.start()
        self.assertTrue(ready.wait(3))
        server = servers[0]
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"

        def post(path, body, bearer=None):
            headers = {"Content-Type": "application/json"}
            if bearer is not None:
                headers["Authorization"] = "Bearer " + bearer
            request = urllib.request.Request(
                base + path, data=json.dumps(body).encode(), headers=headers
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                return json.load(response)

        result = post(
            "/login",
            {
                "username": "remoteauthfixture",
                "password": "fixture-password-only",
                "remember": True,
            },
        )
        self.assertEqual(result["account"]["id"], fixture["id"])
        for key in ("api_token", "game_token", "remember_token"):
            self.assertIsInstance(result[key], str)
        # remote-login persists this exact response; launcher bridge reads api_token.
        game = post("/game-token", {}, result["api_token"])
        self.assertEqual(
            self.store.token(game["game_token"], "game")["account_id"], fixture["id"]
        )
        remembered = post("/remember", {"remember_token": result["remember_token"]})
        self.assertEqual(remembered["account"]["id"], fixture["id"])
        renewed = post("/game-token", {}, remembered["api_token"])
        self.assertEqual(
            self.store.token(renewed["game_token"], "game")["account_id"], fixture["id"]
        )
        with self.assertRaises(urllib.error.HTTPError) as error:
            post("/game-token", {}, "invalid-fixture-bearer")
        # Authentication failures must remain distinct from malformed bodies.
        self.assertEqual(error.exception.code, 401)
        for path, body, expected in (
            ("/remember", {"remember_token": "invalid-fixture-remember"}, 401),
            (
                "/login",
                {"username": "remoteauthfixture", "password": "wrong-fixture-password"},
                401,
            ),
            ("/login", {"username": "remoteauthfixture"}, 400),
            ("/login", {"username": [], "password": "fixture-password-only"}, 400),
        ):
            with self.subTest(path=path, expected=expected):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    post(path, body)
                self.assertEqual(error.exception.code, expected)
