import json
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from wakfu_server.api import serve_api
from postgres_case import PostgresCase
from wakfu_server.command_permissions import set_admin
from wakfu_server.live_console import LiveConsole
from wakfu_server.global_tasks import GlobalTasks


def insert_character(store, account_id, name):
    """Keep API authorization fixtures independent from the optional native catalog."""
    with store.connection() as db:
        return db.execute(
            "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
            "VALUES(%s,%s,%s,1,false,0,0,'[]','{}',100,100) RETURNING id",
            (account_id, name, name.casefold()),
        ).fetchone()["id"]


class ApiAuthorizationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.admin = self.store.register("administrator", "password")["id"]
        self.other = self.store.register("otheradmin", "password")["id"]
        self.player = self.store.register("ordinary", "password")["id"]
        for account in (self.admin, self.other):
            set_admin(self.store, account, True, operator="test", reason="fixture")
        self.character = insert_character(self.store, self.admin, "Admin Player")
        self.foreign = insert_character(self.store, self.other, "Other Player")
        self.tokens = {
            account: self.store.issue_token(account, "api")
            for account in (self.admin, self.other, self.player)
        }
        self.scheduler_token = self.store.issue_token(self.player, "scheduler")
        self.console = LiveConsole(wait_timeout=0)
        self.console.register(self.character, "lease", account_id=self.admin)
        self.console.register(self.foreign, "foreign", account_id=self.other)
        self.calls = []
        self.tasks = GlobalTasks(
            {"positions_flush": lambda: self.calls.append("flush")}
        )
        ready = threading.Event()
        servers = []

        def on_ready(server):
            servers.append(server)
            ready.set()

        thread = threading.Thread(
            target=serve_api,
            args=(self.store, "127.0.0.1", 0),
            kwargs=dict(
                live_console=self.console,
                global_tasks=self.tasks,
                test_tasks={
                    "position": {"character_id": self.character, "command": "!pos"}
                },
                on_ready=on_ready,
            ),
            daemon=True,
        )
        thread.start()
        self.assertTrue(ready.wait(2))
        server = servers[0]
        self.base = f"http://127.0.0.1:{server.server_port}"
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

    def request(self, path, body=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(
            self.base + path,
            headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        try:
            response = urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as response:
            return response.code, json.load(response)
        with response:
            return response.status, json.load(response)

    def test_every_test_entrypoint_rejects_anonymous_invalid_and_player_without_effects(
        self,
    ):
        cases = [
            ("/test/admin-sessions", None),
            (
                "/test/admin-command",
                {"character_id": self.foreign, "command": "!item 2021 1"},
            ),
            ("/test/sessions", None),
            ("/test/tasks", None),
            ("/test/command/fake", None),
            (
                "/test/command",
                {"character_id": self.character, "command": "!item 2021 1"},
            ),
            ("/test/tasks/position", {"request_id": "position:1"}),
            ("/test/tasks/positions_flush", {"request_id": "positions_flush:1"}),
        ]
        for token, expected in [
            (None, 401),
            ("invalid", 401),
            (self.tokens[self.player], 403),
        ]:
            for path, body in cases:
                with self.subTest(path=path, expected=expected):
                    self.assertEqual(self.request(path, body, token)[0], expected)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.console.receipts, {})
        self.assertEqual(
            self.console.drain(self.character, "lease", self.calls.append), 0
        )
        with self.store.connection() as db:
            items = db.execute(
                "SELECT uid FROM inventory_items WHERE character_id=%s",
                (self.character,),
            ).fetchall()
        self.assertEqual([], items)

    def test_panel_commands_delegate_cross_owner_with_idempotent_real_receipt(self):
        token = self.tokens[self.admin]
        sessions = self.request("/test/admin-sessions", token=token)
        self.assertEqual(sessions[0], 200)
        self.assertEqual(
            {row["character_id"] for row in sessions[1]}, {self.character, self.foreign}
        )
        body = dict(
            character_id=self.foreign,
            command="!item 2021 1",
            request_id="panel-delivery",
        )
        status, receipt = self.request("/test/admin-command", body, token)
        self.assertEqual(status, 202)
        self.assertEqual(receipt["status"], "pending")
        self.assertEqual(
            self.request("/test/admin-command", body, token)[1]["handle"],
            receipt["handle"],
        )
        calls = []
        self.console.drain(
            self.foreign,
            "foreign",
            lambda command, *, authorized_by: calls.append((command, authorized_by)),
        )
        self.assertEqual(calls, [("!item 2021 1", self.admin)])
        self.assertEqual(
            self.request("/test/command/" + receipt["handle"], token=token)[1][
                "status"
            ],
            "completed",
        )
        self.assertEqual(
            self.request(
                "/test/command/" + receipt["handle"], token=self.tokens[self.other]
            )[0],
            403,
        )

    def test_panel_commands_allowlist_scheduler_and_revocation(self):
        token = self.tokens[self.admin]
        for command in (
            "!pos",
            "!kamas 100",
            "!item 2021 1 Other",
            "!tp 1 2 3",
            "!item a 1",
        ):
            with self.subTest(command=command):
                self.assertEqual(
                    self.request(
                        "/test/admin-command",
                        dict(character_id=self.foreign, command=command),
                        token,
                    )[0],
                    400,
                )
        self.assertEqual(
            self.request("/test/admin-sessions", token=self.scheduler_token)[0], 403
        )
        self.assertEqual(
            self.request(
                "/test/admin-command",
                dict(character_id=self.foreign, command="!item 2021 1"),
                self.scheduler_token,
            )[0],
            403,
        )
        receipt = self.request(
            "/test/admin-command",
            dict(character_id=self.foreign, command="!tp 1 2 3 4"),
            token,
        )[1]
        set_admin(
            self.store,
            self.admin,
            False,
            operator="test",
            reason="revoke queued panel action",
        )
        calls = []
        self.console.drain(
            self.foreign, "foreign", lambda command, **kwargs: calls.append(command)
        )
        self.assertEqual(calls, [])
        self.assertEqual(self.console.poll(receipt["handle"])["status"], "failed")

    def test_owner_results_cross_account_and_role_revocation_before_execution(self):
        token = self.tokens[self.admin]
        self.assertEqual(
            self.request(
                "/test/command",
                {"character_id": self.foreign, "command": "!pos"},
                token,
            )[0],
            403,
        )
        status, receipt = self.request(
            "/test/command", {"character_id": self.character, "command": "!pos"}, token
        )
        self.assertEqual(status, 202)
        self.assertEqual(
            self.request(
                "/test/command/" + receipt["handle"], token=self.tokens[self.other]
            )[0],
            403,
        )
        set_admin(
            self.store, self.admin, False, operator="test", reason="revoked queued job"
        )
        self.assertEqual(
            self.request("/test/command/" + receipt["handle"], token=token)[0], 403
        )
        self.console.drain(self.character, "lease", self.calls.append)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.console.poll(receipt["handle"])["status"], "failed")

    def test_revoked_token_cannot_execute_previously_queued_command(self):
        token = self.tokens[self.admin]
        _, receipt = self.request(
            "/test/command", {"character_id": self.character, "command": "!pos"}, token
        )
        self.store.revoke_token(token)
        self.console.drain(self.character, "lease", self.calls.append)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.console.poll(receipt["handle"])["status"], "failed")
        self.assertEqual(self.request("/test/sessions", token=token)[0], 401)

    def test_managed_scheduler_retains_global_only_scope_and_revocation(self):
        import tempfile
        from pathlib import Path
        from wakfu_server.storage.scheduler_credentials import provision

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scheduler-token"
            path.write_text("managed-scheduler-test-" + "x" * 48)
            path.chmod(0o600)
            provision(self.store, path, bootstrap=True)
            self.scheduler_token = path.read_text()
            self.test_scheduler_can_flush_but_cannot_inspect_sessions_or_execute_commands()
            with self.assertRaisesRegex(ValueError, "revoked"):
                provision(self.store, path, bootstrap=True)

    def test_scheduler_can_flush_but_cannot_inspect_sessions_or_execute_commands(self):
        token = self.scheduler_token
        for path, body in [
            ("/test/sessions", None),
            ("/test/command/fake", None),
            ("/test/command", {"character_id": self.character, "command": "!pos"}),
            ("/test/tasks/position", {"request_id": "position:1"}),
        ]:
            self.assertEqual(self.request(path, body, token)[0], 403)
        status, tasks = self.request("/test/tasks", token=token)
        self.assertEqual(
            (status, tasks), (200, [{"name": "positions_flush", "scope": "global"}])
        )
        for _ in range(2):
            self.assertEqual(
                self.request(
                    "/test/tasks/positions_flush",
                    {"request_id": "positions_flush:1"},
                    token,
                )[0],
                200,
            )
        self.assertEqual(self.calls, ["flush"])
        self.store.revoke_token(token)
        self.assertEqual(
            self.request(
                "/test/tasks/positions_flush",
                {"request_id": "positions_flush:2"},
                token,
            )[0],
            401,
        )
        self.assertEqual(self.calls, ["flush"])

    def test_bad_body_and_public_health(self):
        self.assertEqual(self.request("/health")[0], 200)
        self.assertEqual(
            self.request("/test/command", [], self.tokens[self.admin])[0], 400
        )
        self.assertEqual(self.console.receipts, {})

    def test_health_returns_generic_503_when_storage_connection_fails(self):
        with patch.object(
            self.store, "connection", side_effect=OSError("private db detail")
        ):
            status, body = self.request("/health")
        self.assertEqual(status, 503)
        self.assertEqual(body, {"ok": False, "storage": "postgresql"})
