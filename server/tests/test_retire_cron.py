"""Cron retirement only revokes its registered scope and leaves unrelated keys alone."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock

SPEC = importlib.util.spec_from_file_location(
    "retire_cron", Path(__file__).resolve().parents[1] / "tools/retire_cron.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RetirementTests(unittest.TestCase):
    def database(self, state, token):
        db = MagicMock()
        db.execute.return_value.fetchone.side_effect = [
            dict(value=state) if state is not None else None,
            token,
        ]
        # Advisory-lock execute does not fetch, hence two fetch results suffice.
        database = MagicMock()
        database.connection.return_value.__enter__.return_value = db
        return database, db

    def client(self):
        client = MagicMock()
        client.scan.side_effect = [
            (8, [b"wakfu:cron:{positions_flush}:done:1"]),
            (0, []),
        ]
        return client

    def test_dry_run_does_not_change_credentials_or_keys(self):
        state = dict(account_id=72, digest="digest", enabled=True)
        database, db = self.database(state, dict(account_id=72, kind="scheduler"))
        client = self.client()
        result = MODULE.retire(database, client)
        self.assertFalse(result["applied"])
        self.assertEqual(1, result["cron_keys"])
        self.assertFalse(client.unlink.called)
        self.assertTrue(
            all(
                not c.args[0].startswith(("DELETE", "INSERT", "UPDATE"))
                for c in db.execute.call_args_list
            )
        )
        self.assertTrue(
            all(c.kwargs["match"] == "wakfu:cron:*" for c in client.scan.call_args_list)
        )

    def test_apply_preserves_principal_and_scopes_token_revocation(self):
        state = dict(account_id=72, digest="digest", enabled=True)
        database, db = self.database(state, dict(account_id=72, kind="scheduler"))
        client = self.client()
        MODULE.retire(database, client, apply=True)
        deletes = [
            c for c in db.execute.call_args_list if c.args[0].startswith("DELETE")
        ]
        self.assertEqual(1, len(deletes))
        self.assertIn("kind='scheduler'", deletes[0].args[0])
        self.assertEqual(("digest", 72), deletes[0].args[1])
        client.unlink.assert_called_once_with(b"wakfu:cron:{positions_flush}:done:1")

    def test_ownership_mismatch_fails_before_any_deletion(self):
        state = dict(account_id=72, digest="digest", enabled=True)
        database, db = self.database(state, dict(account_id=99, kind="api"))
        client = self.client()
        with self.assertRaisesRegex(ValueError, "ownership"):
            MODULE.retire(database, client, apply=True)
        client.scan.assert_not_called()
        self.assertTrue(
            all(
                not c.args[0].startswith(("DELETE", "INSERT", "UPDATE"))
                for c in db.execute.call_args_list
            )
        )


if __name__ == "__main__":
    unittest.main()
