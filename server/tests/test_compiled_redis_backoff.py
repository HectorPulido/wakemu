"""Optional cache failures preserve verified database reads and bounded retries."""
from contextlib import contextmanager
import hashlib
import threading
import unittest
from unittest.mock import Mock, patch

from wakfu_server.native_catalog_index import BoundedByteCache

from wakfu_server import native_compiled_catalog as catalog


class Database:
    def __init__(self):
        self.corrupt = False
        self.reads = 0

    @contextmanager
    def connection(self):
        yield self

    def execute(self, sql, params):
        self.reads += 1
        rows = []
        for key in params[2]:
            raw = ('{"value":' + key + "}").encode()
            rows.append(
                dict(
                    record_key=key,
                    ordinal=int(key),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    source_bytes=len(raw),
                    raw=b"corrupt" if self.corrupt else raw,
                )
            )
        return Mock(fetchall=lambda: rows)


class CompiledRedisBackoffTests(unittest.TestCase):
    def backend(self):
        self.db = Database()
        self.redis = Mock()
        self.backend = catalog.CompiledCatalogBackend(
            self.db, lambda: self.redis, cache=BoundedByteCache()
        )
        return self.backend

    def test_failure_skips_fill_and_later_misses_recovers_and_retains_pg_integrity(
        self,
    ):
        backend = self.backend()
        descriptor = dict(revision="a" * 64, collection="fixture", count=10)
        self.redis.eval.side_effect = TimeoutError("unavailable")
        clock = [10.0]
        with patch.object(catalog.time, "monotonic", side_effect=lambda: clock[0]):
            self.assertEqual({1: b'{"value":1}'}, backend.many_bytes(descriptor, [1]))
            self.assertEqual({2: b'{"value":2}'}, backend.many_bytes(descriptor, [2]))
            self.assertEqual(1, self.redis.eval.call_count)
            self.redis.pipeline.assert_not_called()
            self.assertEqual(4, self.db.reads)
            clock[0] = 15.0
            self.redis.eval.side_effect = None
            self.redis.eval.return_value = [None]
            self.assertEqual({3: b'{"value":3}'}, backend.many_bytes(descriptor, [3]))
            self.assertEqual(2, self.redis.eval.call_count)
            self.redis.pipeline.return_value.execute.assert_called_once()
            self.db.corrupt = True
            with self.assertRaisesRegex(
                ValueError, "PostgreSQL record checksum/size mismatch"
            ):
                backend.many_bytes(descriptor, [4])

    def test_one_recovery_probe_and_old_success_cannot_override_new_failure(self):
        backend = self.backend()
        entered, release = threading.Event(), threading.Event()
        results = []

        def slow():
            entered.set()
            self.assertTrue(release.wait(2))
            return "healthy"

        def failure():
            raise TimeoutError("unavailable")

        with patch.object(catalog.time, "monotonic", return_value=10.0):
            worker = threading.Thread(
                target=lambda: results.append(
                    backend._redis_operation(slow, "fallback", phase="read")
                )
            )
            worker.start()
            self.assertTrue(entered.wait(2))
            self.assertEqual(
                "fallback", backend._redis_operation(failure, "fallback", phase="fill")
            )
            release.set()
            worker.join(2)
            self.assertEqual(["healthy"], results)
            operation = Mock(return_value="wrong")
            self.assertEqual(
                "fallback",
                backend._redis_operation(operation, "fallback", phase="read"),
            )
            operation.assert_not_called()
        entered.clear()
        release.clear()
        with patch.object(catalog.time, "monotonic", return_value=15.0):
            worker = threading.Thread(
                target=lambda: backend._redis_operation(slow, None, phase="read")
            )
            worker.start()
            self.assertTrue(entered.wait(2))
            operation = Mock(return_value="wrong")
            self.assertEqual(
                "fallback",
                backend._redis_operation(operation, "fallback", phase="read"),
            )
            operation.assert_not_called()
            release.set()
            worker.join(2)
            self.assertEqual(
                "wrong", backend._redis_operation(operation, "fallback", phase="read")
            )


if __name__ == "__main__":
    unittest.main()
