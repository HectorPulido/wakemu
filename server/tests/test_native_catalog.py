import hashlib
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

from wakfu_server.storage import native_catalog


class NativeCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.path = self.root / "catalog.json"
        self.path.write_bytes(b'{"source":"file"}')
        self.database = MagicMock()
        self.redis = MagicMock()
        self.redis.get.return_value = None
        self.root_patch = patch.object(native_catalog, "DATA_ROOT", self.root)
        self.root_patch.start()
        self.db_patch = patch.object(
            native_catalog, "_database", return_value=self.database
        )
        self.redis_patch = patch.object(
            native_catalog, "_redis", return_value=self.redis
        )
        self.db_patch.start()
        self.redis_patch.start()
        self.release_patch = patch.object(
            native_catalog, "release", return_value="rev-17"
        )
        self.release_patch.start()
        native_catalog._exists.cache_clear()
        native_catalog._decoded.cache_clear()

    def tearDown(self):
        native_catalog._exists.cache_clear()
        native_catalog._decoded.cache_clear()
        self.release_patch.stop()
        self.redis_patch.stop()
        self.db_patch.stop()
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def set_document(self, raw, checksum=None):
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "raw": raw,
            "sha256": checksum
            if checksum is not None
            else hashlib.sha256(raw or b"").hexdigest(),
        }
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.__exit__.return_value = False
        connection.execute.return_value = cursor
        self.database.connection.return_value = connection
        return cursor

    def test_slow_read_reports_only_path_and_stage_timings(self):
        with patch.object(
            native_catalog.time, "monotonic", return_value=2.0
        ), patch.object(native_catalog.LOG, "warning") as log:
            native_catalog._observe_read(
                "combat-maps/527.json",
                "postgres",
                b"private contents",
                1.0,
                pool_ms=600.1256,
            )
        log.assert_called_once()
        self.assertEqual(
            log.call_args.args[1:5], ("combat-maps/527.json", "postgres", 16, 1000.0)
        )
        self.assertNotIn(b"private contents", log.call_args.args)
        self.assertEqual(log.call_args.args[5], {"pool_ms": 600.126})

    def test_fast_read_does_not_emit_slow_catalog_warning(self):
        with patch.object(
            native_catalog.time, "monotonic", return_value=1.01
        ), patch.object(native_catalog.LOG, "warning") as log:
            native_catalog._observe_read("small.json", "redis", b"data", 1.0)
        log.assert_not_called()

    def test_reads_database_document_and_uses_pinned_release(self):
        self.set_document(b'{"source":"database"}')
        self.assertEqual(native_catalog.read_bytes(self.path), b'{"source":"database"}')
        self.assertEqual(
            self.database.connection.return_value.execute.call_args_list[0].args[1],
            ("rev-17", "catalog.json"),
        )

    def test_valid_redis_hit_skips_database_document_query(self):
        raw = b'{"cached":true}'
        digest = hashlib.sha256(raw).hexdigest().encode()
        self.redis.get.return_value = digest + b"\n" + raw

        self.assertEqual(native_catalog.read_bytes(self.path), raw)
        self.database.connection.assert_not_called()
        self.redis.get.assert_called_once_with("wakemu:catalog:rev-17:catalog.json")

    def test_corrupt_redis_entry_falls_back_to_postgres_and_replaces_cache(self):
        raw = b'{"fresh":true}'
        self.redis.get.return_value = b"bad-digest\ncorrupt"
        self.set_document(raw)

        self.assertEqual(native_catalog.read_bytes(self.path), raw)
        self.redis.setex.assert_called_once_with(
            "wakemu:catalog:rev-17:catalog.json",
            native_catalog.CACHE_TTL,
            hashlib.sha256(raw).hexdigest().encode() + b"\n" + raw,
        )

    def test_postgres_checksum_failure_raises(self):
        self.set_document(b"payload", "incorrect")

        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            native_catalog.read_bytes(self.path)
        self.redis.setex.assert_not_called()

    def test_protocol_read_never_falls_back_to_an_existing_file(self):
        self.assertTrue(self.path.is_file())
        self.redis.get.return_value = None
        self.set_document(None)
        self.database.connection.return_value.execute.return_value.fetchone.return_value = (
            None
        )

        with self.assertRaises(FileNotFoundError):
            native_catalog.read_bytes(self.path)

    def test_load_shares_parsed_document_and_reads_bytes_once(self):
        with patch.object(
            native_catalog, "read_bytes", return_value=b'{"items":[1,2]}'
        ) as read_bytes:
            first = native_catalog.load(self.path)
            second = native_catalog.load(self.path)

        self.assertIs(first, second)
        read_bytes.assert_called_once_with(self.root / "catalog.json")

    def test_concurrent_cold_loads_parse_and_read_once(self):
        with patch.object(
            native_catalog, "read_bytes", return_value=b'{"cold":true}'
        ) as read_bytes:
            with ThreadPoolExecutor(max_workers=12) as pool:
                loaded = list(
                    pool.map(lambda _: native_catalog.load(self.path), range(24))
                )

        self.assertTrue(all(document is loaded[0] for document in loaded))
        read_bytes.assert_called_once_with(self.root / "catalog.json")

    def test_decoded_cache_is_separated_by_release_revision(self):
        native_catalog.release.side_effect = ["rev-one", "rev-two"]
        with patch.object(
            native_catalog,
            "read_bytes",
            side_effect=[b'{"revision":1}', b'{"revision":2}'],
        ) as read_bytes:
            first = native_catalog.load(self.path)
            second = native_catalog.load(self.path)

        self.assertEqual(first, {"revision": 1})
        self.assertEqual(second, {"revision": 2})
        self.assertIsNot(first, second)
        self.assertEqual(read_bytes.call_count, 2)

    def test_cache_boundary_and_ttl(self):
        for size, should_cache in (
            (native_catalog.CACHE_MAX_BYTES, True),
            (native_catalog.CACHE_MAX_BYTES + 1, False),
        ):
            with self.subTest(size=size):
                raw = b"x" * size
                self.redis.reset_mock()
                self.redis.get.return_value = None
                self.set_document(raw)

                self.assertEqual(native_catalog.read_bytes(self.path), raw)
                if should_cache:
                    self.redis.setex.assert_called_once()
                    self.assertEqual(
                        self.redis.setex.call_args.args[1], native_catalog.CACHE_TTL
                    )
                else:
                    self.redis.setex.assert_not_called()

    def test_redis_unavailable_falls_back_to_postgres(self):
        raw = b"postgres"
        self.redis.get.side_effect = OSError("offline")
        self.redis.setex.side_effect = OSError("offline")
        self.set_document(raw)

        self.assertEqual(native_catalog.read_bytes(self.path), raw)

    def test_outside_data_root_uses_file_backend(self):
        outside = self.root.parent / "outside-catalog.json"
        outside.write_bytes(b"offline-file")
        try:
            self.assertEqual(native_catalog.read_bytes(outside), b"offline-file")
            self.database.connection.assert_not_called()
            self.redis.get.assert_not_called()
        finally:
            outside.unlink()


if __name__ == "__main__":
    unittest.main()
