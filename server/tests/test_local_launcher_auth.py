import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import unittest
import urllib.error
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / "client-tools/runtime"
sys.path.insert(0, str(TOOLS))
from local_launcher_auth import LauncherAuthentication, LauncherAuthenticationError


class LocalLauncherAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.login = Path(self.directory.name) / "login-session.json"
        self.login.write_text(
            json.dumps({"api_token": "expired", "account": {"id": 7}})
        )

    def response(self, body):
        return io.BytesIO(json.dumps(body).encode())

    def test_401_renews_revocable_token_then_retries_and_writes_private_session(self):
        self.login.with_name("remember.json").write_text(
            json.dumps({"token": "revocable"})
        )
        calls = []

        def request(req, timeout):
            calls.append(
                (req.full_url, req.get_header("Authorization"), json.loads(req.data))
            )
            if len(calls) == 1:
                raise urllib.error.HTTPError(req.full_url, 401, "expired", {}, None)
            if len(calls) == 2:
                return self.response({"api_token": "renewed", "account": {"id": 7}})
            return self.response({"game_token": "game"})

        auth = LauncherAuthentication(self.login, opener=request)
        self.assertEqual(auth.game_token(), "game")
        self.assertEqual(calls[1][2], {"remember_token": "revocable"})
        self.assertEqual(calls[2][1], "Bearer renewed")
        self.assertEqual(self.login.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(self.login.read_text())["api_token"], "renewed")
        self.assertEqual(
            set(self.login.parent.iterdir()),
            {self.login, self.login.with_name("remember.json")},
        )

    def test_every_request_rereads_replaced_login(self):
        calls = []

        def request(req, timeout):
            calls.append(req.get_header("Authorization"))
            return self.response({"game_token": "game"})

        auth = LauncherAuthentication(self.login, opener=request)
        auth.game_token()
        self.login.write_text(json.dumps({"api_token": "fresh"}))
        auth.game_token()
        self.assertEqual(calls, ["Bearer expired", "Bearer fresh"])

    def test_missing_or_revoked_remember_preserves_session(self):
        original = self.login.read_bytes()

        def reject(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 401, "secret body", {}, None)

        for remembered in (False, True):
            if remembered:
                self.login.with_name("remember.json").write_text(
                    json.dumps({"token": "revocable"})
                )
            with self.subTest(remembered=remembered), self.assertRaises(
                LauncherAuthenticationError
            ):
                LauncherAuthentication(self.login, opener=reject).game_token()
            self.assertEqual(self.login.read_bytes(), original)

    def test_different_account_renewal_rejects_without_overwriting(self):
        self.login.with_name("remember.json").write_text(
            json.dumps({"token": "revocable"})
        )
        original = self.login.read_bytes()

        def request(req, timeout):
            if req.full_url.endswith("/game-token"):
                raise urllib.error.HTTPError(req.full_url, 401, "expired", {}, None)
            return self.response({"api_token": "foreign", "account": {"id": 8}})

        with self.assertRaises(LauncherAuthenticationError):
            LauncherAuthentication(self.login, opener=request).game_token()
        self.assertEqual(self.login.read_bytes(), original)

    def test_authentication_failure_returns_rpc_exception_without_closing_connection(
        self,
    ):
        with patch.dict(os.environ, WAKFU_GAME_LOGIN_FILE=str(self.login)):
            spec = importlib.util.spec_from_file_location(
                "launcher_bridge_test", TOOLS / "local-launcher-bridge.py"
            )
            bridge = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bridge)
        bridge.AUTH.game_token = lambda: (_ for _ in ()).throw(
            LauncherAuthenticationError("sign in again")
        )
        server, client = socket.socketpair()
        self.addCleanup(client.close)
        worker = threading.Thread(target=bridge.serve, args=(server,), daemon=True)
        worker.start()
        args = (
            b"\x0b\x00\x01"
            + bridge.string(bridge.SESSION)
            + b"\x08\x00\x02"
            + struct.pack(">i", 3)
            + b"\x00"
        )
        client.sendall(
            struct.pack(">I", 0x80010001)
            + bridge.string("auth_getGameToken")
            + struct.pack(">i", 1)
            + args
        )
        self.assertEqual(struct.unpack(">I", bridge.receive(client, 4))[0], 0x80010003)
        self.assertEqual(bridge.read_string(client), "auth_getGameToken")
        self.assertEqual(bridge.receive(client, 4), struct.pack(">i", 1))
        self.assertEqual(bridge.receive(client, 3), b"\x0b\x00\x01")
        self.assertEqual(bridge.read_string(client), "sign in again")
        self.assertEqual(
            bridge.receive(client, 8), b"\x08\x00\x02" + struct.pack(">i", 6) + b"\x00"
        )
        args = b"\x0b\x00\x01" + bridge.string(bridge.SESSION) + b"\x00"
        client.sendall(
            struct.pack(">I", 0x80010001)
            + bridge.string("updater_isUpdateAvailable")
            + struct.pack(">i", 2)
            + args
        )
        self.assertEqual(struct.unpack(">I", bridge.receive(client, 4))[0], 0x80010002)
        self.assertEqual(bridge.read_string(client), "updater_isUpdateAvailable")
        self.assertEqual(
            bridge.receive(client, 8), struct.pack(">i", 2) + b"\x02\x00\x00\x00"
        )
        self.assertEqual(bridge.receive(client, 1), b"\x00")
