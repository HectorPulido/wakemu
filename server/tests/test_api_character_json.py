"""Native character bytes stay native while HTTP uses an explicit projection."""
import json
import threading
import unittest
import urllib.error
import urllib.request

from postgres_case import PostgresCase
from wakfu_server.api import character_json, serve_api


class CharacterJsonTests(unittest.TestCase):
    def test_only_native_achievement_section_is_explicitly_encoded(self):
        native = {"id": 9, "achievement_section": b"\x00\xab\xff"}
        projected = character_json(native)
        self.assertEqual(
            json.loads(json.dumps(projected))["achievement_section"], "00abff"
        )
        self.assertEqual(native["achievement_section"], b"\x00\xab\xff")
        self.assertEqual(
            character_json({"achievement_section": b""})["achievement_section"], ""
        )
        self.assertEqual(
            character_json({"achievement_section": None}), {"achievement_section": None}
        )
        self.assertEqual(character_json({"id": 9}), {"id": 9})
        with self.assertRaises(TypeError):
            json.dumps(character_json({"unexpected_native_bytes": b"\xab"}))
        for invalid in ("00ab", bytearray(b"\xab"), 3):
            with self.subTest(invalid=type(invalid).__name__), self.assertRaises(
                TypeError
            ):
                character_json({"achievement_section": invalid})


class CharacterJsonPostgresTests(PostgresCase):
    def test_real_http_creation_and_listing_preserve_native_bytes_without_duplicate_commit(
        self,
    ):
        ready = threading.Event()
        servers = []

        def on_ready(server):
            servers.append(server)
            ready.set()

        thread = threading.Thread(
            target=serve_api,
            args=(self.store, "127.0.0.1", 0),
            kwargs={"on_ready": on_ready},
            daemon=True,
        )
        thread.start()
        self.assertTrue(ready.wait(5))
        server = servers[0]
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"

        def request(path, body=None, token=None):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = "Bearer " + token
            outgoing = urllib.request.Request(
                base + path,
                headers=headers,
                data=None if body is None else json.dumps(body).encode(),
            )
            try:
                incoming = urllib.request.urlopen(outgoing, timeout=20)
            except urllib.error.HTTPError as incoming:
                return incoming.code, json.load(incoming)
            with incoming:
                return incoming.status, json.load(incoming)

        status, account = request(
            "/register",
            {"username": "json-character-owner", "password": "test-password"},
        )
        self.assertEqual(status, 201)
        status, login = request(
            "/login", {"username": "json-character-owner", "password": "test-password"}
        )
        self.assertEqual(status, 200)
        token = login["api_token"]
        status, created = request(
            "/characters", {"name": "Json Native", "breed": 8}, token
        )
        self.assertEqual(status, 201, created)
        native = self.store.character(account["id"], created["id"])
        self.assertIs(type(native["achievement_section"]), bytes)
        self.assertEqual(
            created["achievement_section"], native["achievement_section"].hex()
        )
        self.assertEqual(
            bytes.fromhex(created["achievement_section"]), native["achievement_section"]
        )
        status, listed = request("/characters", token=token)
        self.assertEqual(status, 200, listed)
        self.assertEqual([row["id"] for row in listed], [created["id"]])
        self.assertEqual(
            listed[0]["achievement_section"], native["achievement_section"].hex()
        )
        with self.store.connection() as db:
            count = db.execute(
                "SELECT count(*) AS n FROM characters WHERE account_id=%s",
                (account["id"],),
            ).fetchone()["n"]
        self.assertEqual(count, 1)
        self.assertEqual(
            self.reopen().character(account["id"], created["id"])[
                "achievement_section"
            ],
            native["achievement_section"],
        )
