import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from wakfu_ai.native.native_database import connection
from wakfu_ai.native.native_deadline import bounded


class NativeDatabaseTests(unittest.TestCase):
    def test_pool_and_statements_use_remaining_deadline(self):
        queries, waits = [], []

        class DB:
            @contextmanager
            def transaction(self):
                yield

            def execute(self, query, *args, **kwargs):
                queries.append((query, args))
                return "result"

        class Pool:
            @contextmanager
            def connection(self, *, timeout):
                waits.append(timeout)
                yield DB()

        store = SimpleNamespace(database=SimpleNamespace(pool=Pool()))
        with bounded(12, clock=lambda: 10):
            with connection(store) as db:
                db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                self.assertEqual(db.execute("SELECT complete_authorities"), "result")
        self.assertEqual(waits, [2])
        self.assertEqual(
            queries[0][0], "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
        )
        self.assertIn("statement_timeout", queries[1][0])
        self.assertEqual(queries[1][1], (("2000",),))

    def test_expired_deadline_never_acquires_connection(self):
        with self.assertRaises(TimeoutError):
            with bounded(9, clock=lambda: 10):
                with connection(None):
                    self.fail("expired scope acquired database")
