"""Focused contract tests for the bot World bridge and its internal HTTP routes."""

import json
import threading
import unittest
import urllib.error
import urllib.request

from wakfu_server.api import serve_api
from wakfu_server.bots.bridge import BotConflict, BotWorldBridge


class FakeRuntime:
    supported_actions = ("create", "activate", "deactivate", "say")

    def __init__(self):
        self.calls = []
        self.deactivated = 0
        self.heartbeats = 0

    def snapshot(self):
        return [{"bot_id": "bot-1", "active": True}]

    def execute(self, bot_id, action, args):
        self.calls.append((bot_id, action, args))
        return {"accepted": True, "count": len(self.calls)}

    def heartbeat(self):
        self.heartbeats += 1

    def deactivate_all(self):
        self.deactivated += 1


class BotWorldBridgeTests(unittest.TestCase):
    def setUp(self):
        self.now = [1000.0]
        self.runtime = FakeRuntime()
        self.bridge = BotWorldBridge(
            self.runtime,
            "dedicated-bot-credential-123456",
            clock=lambda: self.now[0],
            event_limit=2,
            worker_timeout=5,
        )

    def command(self, **overrides):
        body = {
            "world_epoch": self.bridge.epoch,
            "request_id": "request-1",
            "issued_at": self.now[0],
            "bot_id": "bot-1",
            "action": "say",
            "args": {"text": "hello"},
        }
        body.update(overrides)
        return body

    def test_idempotent_receipt_and_epoch_fence(self):
        first = self.bridge.command(self.command())
        replay = self.bridge.command(self.command(issued_at=self.now[0] + 1))
        self.assertEqual(first, replay)
        self.assertEqual(len(self.runtime.calls), 1)
        with self.assertRaises(BotConflict):
            self.bridge.command(self.command(args={"text": "different"}))
        with self.assertRaises(BotConflict):
            self.bridge.command(self.command(world_epoch="old-world"))
        with self.assertRaises(ValueError):
            self.bridge.command(self.command(action="say", args={"text": float("nan")}))

    def test_event_replay_detects_expired_cursor_and_wrong_epoch(self):
        self.bridge.emit("bot-1", "chat.message", {"text": "one"})
        self.bridge.emit("bot-1", "chat.message", {"text": "two"})
        page = self.bridge.poll(0, self.bridge.epoch)
        self.assertEqual([event["id"] for event in page["events"]], [1, 2])
        self.bridge.emit("bot-1", "chat.message", {"text": "three"})
        with self.assertRaises(BotConflict):
            self.bridge.poll(0, self.bridge.epoch)
        with self.assertRaises(BotConflict):
            self.bridge.poll(2, "stale-epoch")

    def test_worker_watchdog_deactivates_after_timeout(self):
        self.bridge.tick()
        self.assertEqual(self.runtime.deactivated, 1)
        self.bridge.snapshot()
        self.bridge.tick()
        self.assertEqual(self.runtime.heartbeats, 1)
        self.now[0] += 6
        self.bridge.tick()
        self.assertEqual(self.runtime.deactivated, 2)


class BotWorldHttpTests(unittest.TestCase):
    def setUp(self):
        self.bridge = BotWorldBridge(FakeRuntime(), "dedicated-bot-credential-123456")
        self.ready = threading.Event()
        servers = []

        def on_ready(server):
            servers.append(server)
            self.ready.set()

        self.thread = threading.Thread(
            target=serve_api,
            args=(object(), "127.0.0.1", 0),
            kwargs={"bots_bridge": self.bridge, "on_ready": on_ready},
            daemon=True,
        )
        self.thread.start()
        self.assertTrue(self.ready.wait(2), "World API did not become ready")
        self.server = servers[0]
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(
        self, method, path, *, token="dedicated-bot-credential-123456", body=None
    ):
        headers = {}
        data = None
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        req = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        try:
            response = urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.load(error)
        with response:
            return response.code, json.load(response)

    def test_exact_bearer_protects_snapshot_and_commands(self):
        for token in (
            None,
            "dedicated-bot-credential-123456-suffix",
            "bearer dedicated-bot-credential-123456",
        ):
            with self.subTest(token=token):
                self.assertEqual(
                    self.request("GET", "/internal/bots/snapshot", token=token)[0], 401
                )
        status, snapshot = self.request("GET", "/internal/bots/snapshot")
        self.assertEqual(status, 200)
        self.assertEqual(snapshot["world_epoch"], self.bridge.epoch)
        self.assertEqual(snapshot["bots"][0]["bot_id"], "bot-1")
        self.assertEqual(self.request("GET", "/internal/bots/unknown")[0], 404)

    def test_commands_map_conflicts_and_reject_malformed_bodies(self):
        body = {
            "world_epoch": self.bridge.epoch,
            "request_id": "http-request-1",
            "issued_at": self.bridge.clock(),
            "bot_id": "bot-1",
            "action": "say",
            "args": {"text": "hello"},
        }
        self.assertEqual(
            self.request("POST", "/internal/bots/commands", body=body)[0], 200
        )
        body["world_epoch"] = "stale"
        status, payload = self.request("POST", "/internal/bots/commands", body=body)
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"], "world_epoch_changed")
        self.assertEqual(
            self.request("POST", "/internal/bots/commands", body=[])[0], 400
        )


if __name__ == "__main__":
    unittest.main()
