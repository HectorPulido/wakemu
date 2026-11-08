import time
import unittest
from unittest.mock import patch

from wakfu_server import native_cache_fill_batch as batch
import test_retained_replay_metadata_batch as fixtures


class FillBatchTests(unittest.TestCase):
    def fixture(self, **kwargs):
        case = fixtures.RetainedReplayMetadataBatchTests()
        return case.fixture(size=3, **kwargs)

    def test_actual_verified_reader_batches_fills_but_reads_stay_immediate(self):
        data = self.fixture()
        redis = data.reader.backend.redis_provider()
        with patch.object(redis, "execute", wraps=redis.execute) as writes:
            with batch.verified_cache_fill_scope():
                first = data.reader["1"]
                with batch.verified_cache_fill_scope():
                    second = data.reader["2"]
                    third = data.reader["3"]
                self.assertEqual(writes.call_count, 0)
                self.assertEqual(len(data.state["payload"]), 3)
                self.assertEqual(data.reader["1"], first)
                self.assertIsNot(data.reader["1"], first)
                self.assertEqual(len(data.state["payload"]), 3)
            self.assertEqual(writes.call_count, 1)
        self.assertEqual(
            [first, second, third], [data.values[str(i)] for i in range(1, 4)]
        )
        # Outside the wave scope the existing synchronous behavior remains.
        other = self.fixture()
        redis = other.reader.backend.redis_provider()
        with patch.object(redis, "execute", wraps=redis.execute) as writes:
            other.reader["1"]
            other.reader["2"]
            self.assertEqual(writes.call_count, 2)

    def test_nested_scope_exception_reset_and_both_bounds(self):
        class Backend:
            def __init__(self):
                self.calls = []

            def _fill_cached_records(self, rows):
                self.calls.append(tuple(rows))

        backend = Backend()
        with self.assertRaisesRegex(ValueError, "gameplay failure"):
            with batch.verified_cache_fill_scope():
                for index in range(129):
                    batch.fill_or_defer(backend, [(str(index), b"x")])
                self.assertEqual([len(r) for r in backend.calls], [128])
                raise ValueError("gameplay failure")
        self.assertEqual([len(r) for r in backend.calls], [128, 1])
        self.assertIsNone(batch._ACTIVE.get())
        backend = Backend()
        with patch.object(batch, "_MAX_BYTES", 8):
            with batch.verified_cache_fill_scope():
                batch.fill_or_defer(backend, [("a", b"1234"), ("b", b"1234")])
                self.assertEqual(len(backend.calls), 1)
            self.assertEqual(len(backend.calls), 2)

    def test_authority_corruption_and_existing_redis_cooldown_are_preserved(self):
        data = self.fixture(corrupt="2")
        redis = data.reader.backend.redis_provider()
        with patch.object(redis, "execute", wraps=redis.execute) as writes:
            with self.assertRaisesRegex(ValueError, "checksum/size mismatch"):
                with batch.verified_cache_fill_scope():
                    data.reader["1"]
                    data.reader["2"]
            self.assertEqual(writes.call_count, 1)
        self.assertIsNone(batch._ACTIVE.get())
        data = self.fixture()
        backend = data.reader.backend
        redis = backend.redis_provider()
        redis.fail = True
        with patch.object(redis, "execute", wraps=redis.execute) as writes:
            with batch.verified_cache_fill_scope():
                data.reader["1"]
            self.assertEqual(writes.call_count, 1)
            self.assertGreater(backend._redis_retry_at, time.monotonic())
            with batch.verified_cache_fill_scope():
                data.reader["2"]
            self.assertEqual(writes.call_count, 1)
        self.assertEqual(len(data.state["payload"]), 2)
