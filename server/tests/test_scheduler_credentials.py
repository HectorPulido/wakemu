"""Managed cron registration must persist without bypassing operator revocation."""
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.storage.scheduler_credentials import provision, SETTING


class SchedulerCredentialTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "token"
        self.path.write_text("test-scheduler-credential-" + "x" * 40)
        self.path.chmod(0o600)

    def state(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT value FROM settings WHERE name=%s", (SETTING,)
            ).fetchone()["value"]

    def test_initial_registration_and_restart_keep_same_nonadmin_owner(self):
        self.assertTrue(provision(self.store, self.path, bootstrap=True)["created"])
        first = self.state()
        self.assertFalse(provision(self.reopen(), self.path, bootstrap=True)["created"])
        self.assertEqual(first, self.state())
        access = self.store.token(self.path.read_text(), "scheduler")
        self.assertEqual(access["account_id"], first["account_id"])
        with self.store.connection() as db:
            row = db.execute(
                "SELECT is_admin FROM accounts WHERE id=%s", (first["account_id"],)
            ).fetchone()
        self.assertFalse(row["is_admin"])
        with self.assertRaises(ValueError):
            self.store.token(self.path.read_text(), "api")

    def test_credential_is_renewed_before_expiry_without_changing_file(self):
        provision(self.store, self.path, bootstrap=True)
        original = self.path.read_bytes()
        with self.store.connection() as db:
            db.execute(
                "UPDATE tokens SET expires_at=%s WHERE digest=%s",
                (
                    datetime.now(timezone.utc) + timedelta(minutes=1),
                    self.state()["digest"],
                ),
            )
        self.assertTrue(provision(self.store, self.path)["renewed"])
        self.assertEqual(original, self.path.read_bytes())
        self.assertFalse(provision(self.store, self.path)["renewed"])

    def test_disabled_registration_is_not_reenabled_on_restart(self):
        provision(self.store, self.path, bootstrap=True)
        state = self.state()
        state["enabled"] = False
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s", (Jsonb(state), SETTING)
            )
        with self.assertRaisesRegex(ValueError, "disabled"):
            provision(self.reopen(), self.path, bootstrap=True)
        self.assertFalse(self.state()["enabled"])

    def test_revoked_token_is_not_recreated_on_restart(self):
        provision(self.store, self.path, bootstrap=True)
        self.store.revoke_token(self.path.read_text())
        with self.assertRaisesRegex(ValueError, "revoked"):
            provision(self.reopen(), self.path, bootstrap=True)

    def test_changed_or_public_secret_is_rejected(self):
        provision(self.store, self.path, bootstrap=True)
        first = self.state()
        self.path.write_text("different-scheduler-credential-" + "z" * 40)
        with self.assertRaisesRegex(ValueError, "differs"):
            provision(self.store, self.path, bootstrap=True)
        self.assertEqual(first, self.state())
        self.path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "private"):
            provision(self.store, self.path)

    def test_existing_scheduler_credential_keeps_its_scoped_owner(self):
        account = self.store.register("existingservice", "private-test-password")["id"]
        token = self.store.issue_token(account, "scheduler")
        self.path.write_text(token)
        provision(self.store, self.path, bootstrap=True)
        self.assertEqual(self.state()["account_id"], account)
        self.assertEqual(self.store.token(token, "scheduler")["account_id"], account)

    def test_banned_service_account_cannot_be_renewed(self):
        provision(self.store, self.path, bootstrap=True)
        state = self.state()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_bans(account_id,reason,operator,banned_at) "
                "VALUES(%s,'test','test',CURRENT_TIMESTAMP)",
                (state["account_id"],),
            )
        with self.assertRaisesRegex(ValueError, "banned"):
            provision(self.store, self.path, bootstrap=True)
