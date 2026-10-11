"""Ban enforcement across every persisted access credential and session lease."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import threading
from contextlib import contextmanager
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server.admin_domain import AdminService


class AccountBanTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("ban_fixture", "test-password")["id"]
        self.admin = AdminService(self.store)

    def test_permanent_ban_revokes_all_credentials_and_session_then_unban_requires_login(
        self,
    ):
        tokens = {
            kind: self.store.issue_token(self.account, kind)
            for kind in ("remember", "api", "game", "ticket", "scheduler")
        }
        generation = self.store.begin_session(self.account)
        self.admin.ban_account(self.account, {"reason": "Fixture sanction"}, "operator")
        self.assertTrue(self.admin.account(self.account)["banned"])
        self.assertFalse(self.store.current_session(self.account, generation))
        self.assertFalse(
            self.store.session_health(self.account, generation, renew=True)["valid"]
        )
        self.assertFalse(self.store.heartbeat(self.account, generation))
        for kind, token in tokens.items():
            with self.assertRaises(ValueError):
                self.store.token(token, kind)
            with self.assertRaises(ValueError):
                self.store.issue_token(self.account, kind)
        with self.assertRaises(ValueError):
            self.store.authenticate("ban_fixture", "test-password")
        with self.assertRaises(ValueError):
            self.store.begin_session(self.account)
        self.admin.unban_account(
            self.account, {"reason": "Appeal accepted"}, "operator"
        )
        self.assertEqual(
            self.store.authenticate("ban_fixture", "test-password")["id"], self.account
        )
        for kind, token in tokens.items():
            with self.assertRaises(ValueError):
                self.store.token(token, kind)
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT action,operator FROM admin_panel_audit WHERE target=%s ORDER BY id",
                (str(self.account),),
            ).fetchall()
        self.assertEqual([r["action"] for r in rows], ["account.ban", "account.unban"])
        self.assertTrue(all(r["operator"] == "operator" for r in rows))

    def test_timed_ban_expires_and_persists_across_store_reopen(self):
        now = self.store.clock()
        expires = self.store.now(60)
        self.admin.ban_account(
            self.account,
            {"reason": "Timed fixture", "expires_at": expires.isoformat()},
            "operator",
        )
        reopened = self.reopen()
        with self.assertRaises(ValueError):
            reopened.authenticate("ban_fixture", "test-password")
        reopened.clock = lambda: now + 61
        self.assertEqual(
            reopened.authenticate("ban_fixture", "test-password")["id"], self.account
        )
        self.assertTrue(reopened.issue_token(self.account, "api"))

    def test_concurrent_ban_and_session_creation_cannot_leave_live_access(self):
        gate = threading.Barrier(2)

        def login():
            gate.wait(timeout=5)
            try:
                generation = self.store.begin_session(self.account)
                token = self.store.issue_token(self.account, "game")
                return generation, token
            except ValueError:
                return None

        def ban():
            gate.wait(timeout=5)
            self.admin.ban_account(
                self.account, {"reason": "Concurrent fixture"}, "operator"
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            pending_login = pool.submit(login)
            pending_ban = pool.submit(ban)
            pending_ban.result(timeout=10)
            access = pending_login.result(timeout=10)
        if access:
            generation, token = access
            self.assertFalse(self.store.current_session(self.account, generation))
            with self.assertRaises(ValueError):
                self.store.token(token, "game")
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM sessions WHERE account_id=%s", (self.account,)
                ).fetchone()
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM tokens WHERE account_id=%s", (self.account,)
                ).fetchone()
            )

    def test_ban_waiting_for_live_lease_allows_inflight_account_foreign_key_write(self):
        generation = self.store.begin_session(self.account)
        deleting_session = threading.Event()
        original_connection = self.store.connection

        @contextmanager
        def observed_connection():
            with original_connection() as db:

                class ObservedDB:
                    def execute(inner, sql, params=None):
                        if sql == "DELETE FROM sessions WHERE account_id=%s":
                            deleting_session.set()
                        return db.execute(sql, params)

                yield ObservedDB()

        # Reproduce the real ordering: gameplay owns the session lease, while
        # the ban owns the account guard and waits to revoke that same lease.
        with ThreadPoolExecutor(max_workers=1) as pool:
            with original_connection() as db:
                db.execute("SET LOCAL lock_timeout='2s'")
                db.execute(
                    "SELECT 1 FROM sessions WHERE account_id=%s FOR UPDATE",
                    (self.account,),
                )
                with patch.object(self.store, "connection", observed_connection):
                    pending_ban = pool.submit(
                        self.admin.ban_account,
                        self.account,
                        {"reason": "In-flight operation fixture"},
                        "operator",
                    )
                    self.assertTrue(deleting_session.wait(timeout=5))
                    # The account FK takes KEY SHARE. It must not wait for the
                    # sanction lock, which is itself waiting for this session.
                    db.execute(
                        "INSERT INTO account_professions(account_id,profession_id) VALUES(%s,99999)",
                        (self.account,),
                    )
            pending_ban.result(timeout=10)
        self.assertFalse(self.store.current_session(self.account, generation))
        with self.assertRaisesRegex(ValueError, "Account banned"):
            self.store.issue_token(self.account, "game")

    def test_invalid_ban_does_not_revoke_session(self):
        generation = self.store.begin_session(self.account)
        for data in (
            {"reason": " "},
            {"reason": "x", "expires_at": "2030-01-01"},
            {
                "reason": "x",
                "expires_at": (self.store.now() - timedelta(seconds=1)).isoformat(),
            },
            {"reason": "x", "unknown": True},
        ):
            with self.assertRaises(ValueError):
                self.admin.ban_account(self.account, data, "operator")
        self.assertTrue(self.store.current_session(self.account, generation))
