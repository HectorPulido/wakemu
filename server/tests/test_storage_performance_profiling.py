"""Storage timing preserves pool and transaction failure semantics."""
from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import Mock, patch

from wakfu_server.storage.postgres import Database
from wakfu_server.storage import native_catalog


class StoragePerformanceProfilingTests(TestCase):
    def database(self, *, acquisition_error=None, commit_error=None):
        events = []
        connection = Mock()

        @contextmanager
        def transaction():
            events.append("begin")
            try:
                yield
                if commit_error:
                    raise commit_error
            finally:
                events.append("transaction_exit")

        @contextmanager
        def acquire(*, timeout):
            events.append(("acquire", timeout))
            if acquisition_error:
                raise acquisition_error
            try:
                yield connection
            finally:
                events.append("release")

        connection.transaction = transaction
        db = object.__new__(Database)
        db.pool = Mock()
        db.pool.connection = acquire
        return db, connection, events

    @patch("wakfu_server.storage.postgres.PROFILER")
    def test_success_separates_pool_wait_and_transaction(self, profiler):
        db, connection, events = self.database()
        with patch(
            "wakfu_server.storage.postgres.time.monotonic", side_effect=[1, 3, 4, 9]
        ):
            with db.connection(timeout=0.25) as actual:
                self.assertIs(actual, connection)
                events.append("body")
        self.assertEqual(
            events, [("acquire", 0.25), "begin", "body", "transaction_exit", "release"]
        )
        self.assertEqual(
            profiler.observe.call_args_list[0].args, ("postgres.pool_wait", 2)
        )
        self.assertEqual(
            profiler.observe.call_args_list[1].args, ("postgres.transaction", 5)
        )
        self.assertFalse(profiler.observe.call_args_list[1].kwargs["error"])

    @patch("wakfu_server.storage.postgres.PROFILER")
    def test_acquisition_error_is_preserved_without_transaction(self, profiler):
        original = TimeoutError("pool unavailable")
        db, _, events = self.database(acquisition_error=original)
        with self.assertRaises(TimeoutError) as caught:
            with db.connection():
                self.fail("must not yield")
        self.assertIs(caught.exception, original)
        self.assertEqual(events, [("acquire", None)])
        profiler.observe.assert_called_once()
        self.assertEqual(profiler.observe.call_args.args[0], "postgres.pool_wait")
        self.assertTrue(profiler.observe.call_args.kwargs["error"])

    @patch("wakfu_server.storage.postgres.PROFILER")
    def test_commit_error_marks_transaction_and_releases_connection(self, profiler):
        original = RuntimeError("commit failed")
        db, _, events = self.database(commit_error=original)
        with self.assertRaises(RuntimeError) as caught:
            with db.connection():
                pass
        self.assertIs(caught.exception, original)
        self.assertEqual(events[-1], "release")
        self.assertTrue(profiler.observe.call_args.kwargs["error"])

    @patch("wakfu_server.storage.postgres.PROFILER")
    def test_diagnostics_failure_cannot_mask_body_exception(self, profiler):
        profiler.observe.side_effect = RuntimeError("diagnostics failed")
        original = ValueError("original body error")
        db, _, events = self.database()
        with self.assertRaises(ValueError) as caught:
            with db.connection():
                raise original
        self.assertIs(caught.exception, original)
        self.assertEqual(events[-1], "release")

    @patch("wakfu_server.storage.performance_profiler.PROFILER")
    def test_catalog_reuses_existing_stages_without_document_labels(self, profiler):
        with patch.object(native_catalog.time, "monotonic", return_value=10.1):
            native_catalog._observe_read(
                "private-document.json",
                "postgres",
                b"secret",
                10,
                redis_ms=3,
                pool_ms=7,
                query_ms=12,
            )
        self.assertEqual(
            [call.args[0] for call in profiler.observe.call_args_list],
            ["catalog.read.postgres", "catalog.redis", "catalog.query"],
        )
