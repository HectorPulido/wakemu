"""Verify the actual HTTP clients and profile-management endpoint together."""

import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from wakfu_server.api import serve_api
from wakfu_server.bots.bridge import BotWorldBridge

BOT_SERVICE_ROOT = Path(__file__).resolve().parents[1] / "bot-service"
if str(BOT_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_SERVICE_ROOT))

from wakfu_bots.clients import WorldClient
from wakfu_bots.config import Profiles
from wakfu_bots.http import make_server
from wakfu_bots.runtime import Worker


class RuntimeStub:
    supported_actions = ("say",)

    def __init__(self):
        self.commands = []

    def snapshot(self):
        return []

    def execute(self, bot_id, action, args):
        self.commands.append((bot_id, action, args))
        return {"accepted": True}

    def heartbeat(self):
        pass

    def deactivate_all(self):
        pass


class BotHttpTests(unittest.TestCase):
    def serve_world(self, bridge):
        ready = threading.Event()
        servers = []

        def on_ready(server):
            servers.append(server)
            ready.set()

        thread = threading.Thread(
            target=serve_api,
            args=(object(), "127.0.0.1", 0),
            kwargs={"bots_bridge": bridge, "on_ready": on_ready},
            daemon=True,
        )
        thread.start()
        self.assertTrue(ready.wait(2))
        server = servers[0]
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 2)
        return f"http://127.0.0.1:{server.server_port}"

    def test_world_client_round_trips_snapshot_events_and_idempotent_command(self):
        runtime = RuntimeStub()
        bridge = BotWorldBridge(runtime, "dedicated-bot-credential-123456")
        base = self.serve_world(bridge)
        client = WorldClient(base, "dedicated-bot-credential-123456")

        snapshot = client.snapshot()
        self.assertEqual(bridge.epoch, snapshot["world_epoch"])
        bridge.emit("bot-1", "chat.message", {"text": "test"})
        events = client.events(snapshot["cursor"])
        self.assertEqual(
            ["chat.message"], [event["type"] for event in events["events"]]
        )

        request_id = "stable-command-1"
        first = client.command(
            "bot-1", "say", {"text": "hello"}, request_id, issued_at=time.time()
        )
        retry = client.command(
            "bot-1", "say", {"text": "hello"}, request_id, issued_at=time.time()
        )
        self.assertEqual(first, retry)
        self.assertEqual([("bot-1", "say", {"text": "hello"})], runtime.commands)

    def test_management_http_authenticates_and_persists_profile_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            profiles = Profiles(Path(directory) / "profiles.json")
            worker = Worker(
                profiles, object(), state_path=Path(directory) / "worker.json"
            )
            server = make_server(
                worker, "separate-management-credential-123456", port=0
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.shutdown)
            self.addCleanup(server.server_close)
            self.addCleanup(thread.join, 2)
            base = f"http://127.0.0.1:{server.server_port}"

            def request(method, path, *, token=None, body=None):
                headers = {}
                raw = None
                if token is not None:
                    headers["Authorization"] = "Bearer " + token
                if body is not None:
                    raw = json.dumps(body).encode()
                    headers["Content-Type"] = "application/json"
                req = urllib.request.Request(
                    base + path, data=raw, headers=headers, method=method
                )
                try:
                    response = urllib.request.urlopen(req, timeout=3)
                except urllib.error.HTTPError as error:
                    with error:
                        return error.code, json.load(error)
                with response:
                    return response.code, json.load(response)

            profile = {
                "bot_id": "bot_one",
                "character": {"name": "Merchant", "breed": 15, "sex": 0},
                "enabled": True,
                "capabilities": ["shop"],
                "behaviors": {"buyer": {"purchase_percent": 80}},
            }
            self.assertEqual(401, request("PUT", "/v1/bots/bot_one", body=profile)[0])
            status, saved = request(
                "PUT",
                "/v1/bots/bot_one",
                token="separate-management-credential-123456",
                body=profile,
            )
            self.assertEqual((200, "bot_one"), (status, saved["bot_id"]))
            status, listing = request(
                "GET", "/v1/bots", token="separate-management-credential-123456"
            )
            self.assertEqual((200, "bot_one"), (status, listing["bots"][0]["bot_id"]))
            status, deleted = request(
                "DELETE",
                "/v1/bots/bot_one",
                token="separate-management-credential-123456",
            )
            self.assertEqual((200, True), (status, deleted["removed"]))
            self.assertEqual({}, profiles.snapshot())


if __name__ == "__main__":
    unittest.main()
