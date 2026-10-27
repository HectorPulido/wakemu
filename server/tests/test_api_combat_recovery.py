"""Actual loopback HTTP authentication gates for administrative recovery."""
import json
import threading
import urllib.error
import urllib.request

from postgres_case import PostgresCase
from wakfu_server.api import serve_api
from wakfu_server.combat_admin_recovery import CombatAdminRecovery
from wakfu_server.combat_shared import Registry
from wakfu_server.command_permissions import set_admin
from wakfu_server.position_buffer import Positions


class ApiCombatRecoveryTests(PostgresCase):
    def test_real_http_recovery_requires_current_api_administrator_and_strict_request(
        self,
    ):
        admin = self.store.register("http-recovery-admin", "private-test-password")[
            "id"
        ]
        player = self.store.register("http-recovery-player", "private-test-password")[
            "id"
        ]
        set_admin(
            self.store, admin, True, operator="fixture", reason="HTTP recovery QA"
        )
        tokens = {
            account: self.store.issue_token(account, "api")
            for account in (admin, player)
        }
        scheduler = self.store.issue_token(admin, "scheduler")
        registry = Registry(
            lambda session: self.store.current_character_session(
                session.account_id, session.generation, session.character_id
            )
        )
        positions = Positions(
            self.store, lease_active=self.store.current_character_session
        )
        service = CombatAdminRecovery(self.store, registry, positions)
        ready = threading.Event()
        servers = []

        def on_ready(server):
            servers.append(server)
            ready.set()

        thread = threading.Thread(
            target=serve_api,
            args=(self.store, "127.0.0.1", 0),
            kwargs=dict(combat_recovery=service, on_ready=on_ready),
            daemon=True,
        )
        thread.start()
        self.assertTrue(ready.wait(2))
        server = servers[0]
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = "http://127.0.0.1:" + str(server.server_port)

        def request(body, token):
            headers = {"Content-Type": "application/json"}
            if token is not None:
                headers["Authorization"] = "Bearer " + token
            request = urllib.request.Request(
                base + "/test/admin/combat-recovery",
                data=json.dumps(body).encode(),
                headers=headers,
            )
            try:
                response = urllib.request.urlopen(request, timeout=3)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                return response.status, json.load(response)

        inspect = dict(action="inspect", fight_id=1, character_id=1)
        for token, status in (
            (None, 401),
            ("invalid", 401),
            (tokens[player], 403),
            (scheduler, 403),
        ):
            with self.subTest(expected=status):
                self.assertEqual(request(inspect, token)[0], status)
        self.assertEqual(request(inspect, tokens[admin])[0], 409)
        # The domain's bounded CombatRecoveryRejected is mapped to 409 by
        # the actual API before its generic ValueError/400 branch.
        for body in (
            {},
            dict(inspect, fight_id=True),
            dict(inspect, action="abort"),
            dict(inspect, extra="forbidden"),
        ):
            self.assertEqual(request(body, tokens[admin])[0], 409)
        set_admin(
            self.store,
            admin,
            False,
            operator="fixture",
            reason="revoke live HTTP recovery role",
        )
        self.assertEqual(request(inspect, tokens[admin])[0], 403)
        set_admin(
            self.store, admin, True, operator="fixture", reason="restore isolated role"
        )
        self.store.revoke_token(tokens[admin])
        self.assertEqual(request(inspect, tokens[admin])[0], 401)
        with self.store.connection() as db:
            self.assertFalse(db.execute("SELECT 1 FROM combat_fights").fetchone())
            self.assertFalse(
                db.execute(
                    "SELECT 1 FROM admin_panel_audit WHERE action=%s", (service.ACTION,)
                ).fetchone()
            )
