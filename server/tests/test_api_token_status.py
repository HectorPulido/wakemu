import json
import threading
import unittest
import urllib.error
import urllib.request

from wakfu_server.api import serve_api


class TokenLookupStore:
    def __init__(self):
        self.lookups = []
        self.authentications = []

    def token(self, token, kind):
        self.lookups.append((token, kind))
        raise ValueError("expired or wrong-kind token")

    def authenticate(self, username, password):
        self.authentications.append((username, password))
        raise ValueError("invalid credentials")


class ApiTokenStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = TokenLookupStore()
        ready = threading.Event()
        servers = []

        def on_ready(server):
            servers.append(server)
            ready.set()

        cls.thread = threading.Thread(
            target=serve_api,
            args=(cls.store, "127.0.0.1", 0),
            kwargs={"on_ready": on_ready},
            daemon=True,
        )
        cls.thread.start()
        if not ready.wait(2):
            raise RuntimeError("API test server did not start")
        cls.server = servers[0]
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, method, path, body=None, token=None, raw=None):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        data = (
            raw
            if raw is not None
            else (None if body is None else json.dumps(body).encode())
        )
        request = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        try:
            response = urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as response:
            return response.code, json.load(response)
        with response:
            return response.status, json.load(response)

    def setUp(self):
        self.store.lookups.clear()
        self.store.authentications.clear()

    def test_invalid_missing_expired_wrong_kind_and_wrong_type_tokens_are_401(self):
        self.assertEqual(self.request("GET", "/characters")[0], 401)
        self.assertEqual(self.request("GET", "/characters", token="expired")[0], 401)
        self.assertEqual(
            self.request("POST", "/game-token", body={}, token="wrong-kind")[0], 401
        )
        self.assertEqual(
            self.request("POST", "/remember", body={"remember_token": []})[0], 401
        )
        self.assertIn(("expired", "api"), self.store.lookups)
        self.assertIn(("wrong-kind", "api"), self.store.lookups)
        self.assertNotIn(([], "remember"), self.store.lookups)

    def test_malformed_or_missing_request_fields_remain_400(self):
        self.assertEqual(self.request("POST", "/remember", body={})[0], 400)
        self.assertEqual(self.request("POST", "/remember", raw=b"{")[0], 400)
        self.assertEqual(self.request("POST", "/remember", body=[])[0], 400)
        self.assertEqual(self.store.lookups, [])

    def test_wrong_password_is_401_but_malformed_login_fields_are_400(self):
        self.assertEqual(
            self.request(
                "POST", "/login", body={"username": "alice", "password": "wrong"}
            )[0],
            401,
        )
        self.assertEqual(self.store.authentications, [("alice", "wrong")])

        self.store.authentications.clear()
        for body in (
            {},
            {"username": "alice"},
            {"username": 42, "password": "wrong"},
            {"username": "alice", "password": []},
        ):
            with self.subTest(body=body):
                self.assertEqual(self.request("POST", "/login", body=body)[0], 400)
        self.assertEqual(self.store.authentications, [])


if __name__ == "__main__":
    unittest.main()
