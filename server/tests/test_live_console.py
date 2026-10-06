import json
import queue
import threading
from postgres_case import PostgresCase
from wakfu_server.command_permissions import set_admin
import urllib.request
from wakfu_server.live_console import LiveConsole
from wakfu_server.api import serve_api


class LiveConsoleTests(PostgresCase):
    def test_generation_cancel_owner_thread_and_idempotency(self):
        console = LiveConsole(wait_timeout=0)
        console.register(1, "old")
        result = console.submit(1, "!item 2021 1", request_id="unique")
        self.assertEqual(
            console.submit(1, "!item 2021 1", request_id="unique")["handle"],
            result["handle"],
        )
        errors = []

        def wrong_thread():
            try:
                console.drain(1, "old", lambda text: None)
            except RuntimeError:
                errors.append(True)

        t = threading.Thread(target=wrong_thread)
        t.start()
        t.join()
        self.assertEqual(errors, [True])
        console.register(1, "new")
        self.assertEqual(console.poll(result["handle"])["status"], "cancelled")
        self.assertFalse(console.unregister(1, "old"))
        self.assertEqual(console.drain(1, "old", lambda text: None), 0)
        self.assertEqual(len(console.list_sessions()), 1)

    def test_http_submit_poll_and_session_thread_execution(self):
        store = self.store
        store.clock = lambda: 1000
        account = store.register("apiadmin", "password")["id"]
        store.create_character(account, "API Admin")
        set_admin(store, account, True, operator="test", reason="fixture")
        token = store.issue_token(account, "api")
        console = LiveConsole(wait_timeout=0.02)
        console.register(1, "generation", name="Local", account_id=account)
        ready = queue.Queue()
        thread = threading.Thread(
            target=serve_api,
            args=(store, "127.0.0.1", 0),
            kwargs={"live_console": console, "on_ready": ready.put},
            daemon=True,
        )
        thread.start()
        server = ready.get(timeout=2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"

        def request(path, body=None):
            data = None if body is None else json.dumps(body).encode()
            with urllib.request.urlopen(
                urllib.request.Request(
                    base + path,
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + token,
                    },
                ),
                timeout=2,
            ) as response:
                return response.status, json.load(response)

        self.assertEqual(request("/test/sessions")[1][0]["character_id"], 1)
        status, receipt = request(
            "/test/command",
            {"character_id": 1, "command": "!pos", "request_id": "once"},
        )
        self.assertEqual(status, 202)
        calls = []
        owner = threading.get_ident()

        def execute(command):
            calls.append((command, threading.get_ident()))
            return {"position": [1, 2, 3]}

        self.assertEqual(console.drain(1, "generation", execute), 1)
        result = request("/test/command/" + receipt["handle"])[1]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["result"]["position"], [1, 2, 3])
        self.assertEqual(calls, [("!pos", owner)])
        self.assertEqual(
            request(
                "/test/command",
                {"character_id": 1, "command": "!pos", "request_id": "once"},
            )[1]["handle"],
            receipt["handle"],
        )
        self.assertEqual(console.drain(1, "generation", execute), 0)
