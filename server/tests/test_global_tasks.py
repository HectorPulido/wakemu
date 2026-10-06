import json
import threading
import unittest
from postgres_case import PostgresCase
import urllib.request
import urllib.error
from wakfu_server.global_tasks import GlobalTasks
from wakfu_server.api import serve_api
from wakfu_server.world_scheduler import MemoryBackend, Scheduler


class GlobalTaskTests(PostgresCase):
    def test_whitelist_occurrence_and_failed_retry(self):
        with self.assertRaises(ValueError):
            GlobalTasks({"weather": lambda: None})
        calls = []

        def callback():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("storage unavailable")

        tasks = GlobalTasks({"positions_flush": callback})
        with self.assertRaises(ValueError):
            tasks.run("positions_flush", "builds_flush:1")
        with self.assertRaises(RuntimeError):
            tasks.run("positions_flush", "positions_flush:1")
        self.assertFalse(
            tasks.run("positions_flush", "positions_flush:1")["deduplicated"]
        )
        self.assertTrue(
            tasks.run("positions_flush", "positions_flush:1")["deduplicated"]
        )
        self.assertEqual(len(calls), 2)

    def test_http_global_without_session_and_scheduler_deduplication(self):
        store = self.store
        account = store.register("scheduler", "password")["id"]
        token = store.issue_token(account, "scheduler")
        calls = []
        callbacks = GlobalTasks({"positions_flush": lambda: calls.append(1)})
        ready = threading.Event()
        servers = []

        def on_ready(server):
            servers.append(server)
            ready.set()

        thread = threading.Thread(
            target=serve_api,
            args=(store, "127.0.0.1", 0),
            kwargs=dict(global_tasks=callbacks, on_ready=on_ready),
            daemon=True,
        )
        thread.start()
        self.assertTrue(ready.wait(3))
        base = "http://127.0.0.1:%s" % servers[0].server_port

        def action(occurrence, lost):
            req = urllib.request.Request(
                base + "/test/tasks/positions_flush",
                data=json.dumps({"request_id": occurrence}).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + token,
                },
            )
            with urllib.request.urlopen(req, timeout=2) as response:
                self.assertEqual(json.load(response)["status"], "completed")

        try:
            backend = MemoryBackend(lambda: 1200)
            scheduler = Scheduler(
                backend,
                {"positions_flush": dict(interval=1200, action=action)},
                clock=lambda: 1200,
            )
            self.assertTrue(scheduler.tick()[0]["success"])
            self.assertEqual(scheduler.tick(), [])
            action("positions_flush:1", threading.Event())
            self.assertEqual(calls, [1])
            with urllib.request.urlopen(
                urllib.request.Request(
                    base + "/test/tasks", headers={"Authorization": "Bearer " + token}
                )
            ) as response:
                self.assertEqual(
                    json.load(response),
                    [{"name": "positions_flush", "scope": "global"}],
                )
        finally:
            servers[0].shutdown()
            servers[0].server_close()
            thread.join(2)
