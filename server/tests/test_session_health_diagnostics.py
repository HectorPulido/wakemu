"""Session failure classification uses the same ownership observation as renewal."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import unittest
from wakfu_server.store import Store


class SessionHealthTests(unittest.TestCase):
    def health(self, current, expires_delta, renewed=False, renew=True):
        now = datetime(2026, 10, 8, tzinfo=timezone.utc)
        row = dict(
            generation=current,
            expires_at=None
            if current is None
            else now + timedelta(seconds=expires_delta),
            checked_at=None if current is None else now,
            db_now=now,
            renewed_until=now + timedelta(seconds=300) if renewed else None,
        )

        class Database:
            def execute(inner, sql, params):
                self.assertIn("observed AS MATERIALIZED", sql)
                self.assertIn("o.expires_at>o.checked_at", sql)
                self.assertIn("o.generation=%s", sql)
                inner.params = params
                return inner

            def fetchone(inner):
                return row

        @contextmanager
        def connection():
            yield Database()

        store = Store.__new__(Store)
        store.connection = connection
        store.now = lambda ttl=0: now + timedelta(seconds=ttl)
        return store.session_health(1, "expected-generation", renew=renew)

    def test_missing(self):
        self.assertEqual(self.health(None, 0)["reason"], "missing")

    def test_replaced_not_expired(self):
        result = self.health("replacement", -1)
        self.assertEqual(result["reason"], "replaced")
        self.assertNotIn("replacement", str(result))
        self.assertNotIn("expected-generation", str(result))

    def test_expired_never_renewed(self):
        self.assertEqual(self.health("expected-generation", 0)["reason"], "expired")

    def test_renewal_failure(self):
        self.assertEqual(
            self.health("expected-generation", 20)["reason"], "renewal_failed"
        )

    def test_valid_renewal(self):
        self.assertTrue(self.health("expected-generation", 20, renewed=True)["valid"])

    def test_valid_observation_without_renewal(self):
        self.assertTrue(self.health("expected-generation", 20, renew=False)["valid"])
