"""Atomic chunk reception and complete-manifest verification tests."""
import hashlib
import gzip
import json
import sys
import tempfile
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wakfu_ai.context.context_store import ContextStore


class ContextStoreTests(unittest.TestCase):
    def test_retry_after_publish_then_error_cleans_partial_metadata(self):
        payload = b"published before response failed"
        digest = self.digest(payload)
        original = Path.replace

        def publish_then_error(source, destination):
            original(source, destination)
            raise OSError("failure after publication")

        with patch.object(Path, "replace", publish_then_error):
            with self.assertRaisesRegex(OSError, "after publication"):
                self.store.put(digest, len(payload), 0, payload)
        self.assertTrue(self.store.has(digest))
        self.assertIn(digest, self.store.partial)
        self.assertEqual(
            self.store.put(digest, len(payload), 0, payload),
            {"complete": True, "offset": len(payload)},
        )
        self.assertNotIn(digest, self.store.partial)
        self.assertEqual(self.store.read(digest), payload)

    def test_final_publication_failure_retries_complete_bytes_and_releases_lock(self):
        for payload in (b"", b"complete payload after interrupted publication"):
            with self.subTest(payload=payload):
                digest = self.digest(payload)
                with patch.object(
                    Path, "replace", side_effect=OSError("publication interrupted")
                ):
                    with self.assertRaisesRegex(OSError, "publication interrupted"):
                        self.store.put(digest, len(payload), 0, payload)
                self.assertFalse(self.store.has(digest))
                self.assertEqual(self.store.partial[digest]["offset"], len(payload))
                self.assertEqual(len(self.store._publication_locks), 0)
                self.assertEqual(
                    self.store.put(digest, len(payload), 0, payload),
                    {"complete": True, "offset": len(payload)},
                )
                self.assertEqual(self.store.read(digest), payload)
                self.assertNotIn(digest, self.store.partial)
                self.assertFalse((self.store.root / (digest + ".partial")).exists())

    def test_distinct_uploads_and_imports_verify_concurrently(self):
        for kinds in (("upload", "upload"), ("upload", "import"), ("import", "import")):
            with self.subTest(kinds=kinds):
                payloads = [(str(kinds) + str(index)).encode() for index in range(2)]
                digests = [self.digest(payload) for payload in payloads]
                sources = [self.store.root / (digest + ".source") for digest in digests]
                for source, payload in zip(sources, payloads):
                    source.write_bytes(payload)
                barrier = threading.Barrier(2)
                original = self.store.has

                def overlapping_has(digest, size=None):
                    barrier.wait(timeout=3)
                    return original(digest, size)

                def publish(index):
                    payload, digest = payloads[index], digests[index]
                    if kinds[index] == "upload":
                        self.store.put(digest, len(payload), 0, payload)
                    else:
                        self.store.import_file(sources[index], digest, len(payload))

                with patch.object(self.store, "has", side_effect=overlapping_has):
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        futures = [pool.submit(publish, index) for index in range(2)]
                        for future in futures:
                            future.result(timeout=5)
                for digest, payload in zip(digests, payloads):
                    self.assertEqual(self.store.read(digest), payload)

    def test_same_digest_publication_serializes_upload_and_import(self):
        payload = b"same complete content from two publishers"
        digest = self.digest(payload)
        source = self.store.root / "import-source"
        source.write_bytes(payload)
        entered, release, second_started = (
            threading.Event(),
            threading.Event(),
            threading.Event(),
        )
        original = self.store.has
        calls = []

        def paused_has(checksum, size=None):
            calls.append(checksum)
            if len(calls) == 1:
                entered.set()
                if not release.wait(timeout=3):
                    raise AssertionError("Publication was not released")
            return original(checksum, size)

        def import_same():
            second_started.set()
            self.store.import_file(source, digest, len(payload))

        with patch.object(self.store, "has", side_effect=paused_has):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.store.put, digest, len(payload), 0, payload)
                self.assertTrue(entered.wait(timeout=3))
                second = pool.submit(import_same)
                self.assertTrue(second_started.wait(timeout=3))
                self.assertEqual(calls, [digest])
                release.set()
                self.assertTrue(first.result(timeout=5)["complete"])
                second.result(timeout=5)
        self.assertEqual(calls, [digest, digest])
        self.assertEqual(self.store.read(digest), payload)
        self.assertEqual(self.store.partial, {})
        self.assertEqual(len(self.store._publication_locks), 0)

    def test_independent_complete_hashes_run_concurrently_without_verified_cache(self):
        hashes = [
            self.put_chunks(payload)[0]
            for payload in (b"one-complete-blob", b"two-complete-blobs")
        ]
        barrier = threading.Barrier(2)
        sha256 = hashlib.sha256

        class ConcurrentHash:
            def __init__(self, *args, **kwargs):
                self.hash = sha256(*args, **kwargs)
                self.first = True

            def update(self, payload):
                if self.first:
                    self.first = False
                    barrier.wait(timeout=5)
                self.hash.update(payload)

            def hexdigest(self):
                return self.hash.hexdigest()

        with patch("wakfu_ai.context.context_store.hashlib.sha256", ConcurrentHash):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.store.has, digest) for digest in hashes]
                self.assertEqual(
                    [future.result(timeout=10) for future in futures], [True, True]
                )
        (self.store.root / hashes[0]).write_bytes(b"corrupted-content")
        self.assertFalse(self.store.has(hashes[0]))
        self.assertTrue(self.store.has(hashes[1]))

    def test_complete_reads_hash_once_and_run_independently(self):
        payloads = [b"complete-one", b"complete-two"]
        hashes = [self.put_chunks(payload)[0] for payload in payloads]
        barrier = threading.Barrier(2)
        original = hashlib.sha256
        observed = []

        def concurrent_hash(data):
            observed.append(data)
            barrier.wait(timeout=3)
            return original(data)

        with patch(
            "wakfu_ai.context.context_store.hashlib.sha256", side_effect=concurrent_hash
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.store.read, digest) for digest in hashes]
                self.assertEqual(
                    [future.result(timeout=5) for future in futures], payloads
                )
        self.assertCountEqual(observed, payloads)
        self.store._path(hashes[0]).write_bytes(b"corrupt after verification")
        with self.assertRaisesRegex(ValueError, "changed while reading"):
            self.store.read(hashes[0])

    def test_read_verifies_returned_snapshot_during_atomic_replacement(self):
        payload = b"complete verified snapshot"
        digest, _ = self.put_chunks(payload)
        blob = self.store._path(digest)
        replacement = self.store.root / "replacement"
        replacement.write_bytes(b"corrupt replacement")
        original = Path.read_bytes

        def read_then_replace(path):
            data = original(path)
            if path == blob:
                replacement.replace(blob)
            return data

        with patch.object(Path, "read_bytes", read_then_replace):
            self.assertEqual(self.store.read(digest), payload)
        with self.assertRaisesRegex(ValueError, "changed while reading"):
            self.store.read(digest)

    def test_complete_read_rejects_missing_directory_and_invalid_digest(self):
        digest = self.digest(b"not published")
        with self.assertRaisesRegex(ValueError, "Missing verified"):
            self.store.read(digest)
        self.store._path(digest).mkdir()
        with self.assertRaisesRegex(ValueError, "Missing verified"):
            self.store.read(digest)
        with self.assertRaisesRegex(ValueError, "Invalid context content hash"):
            self.store.read("../invalid")

    def test_has_during_atomic_upload_and_import_never_observes_partial_canonical_blob(
        self,
    ):
        original_replace = Path.replace
        for kind in ("upload", "import"):
            with self.subTest(kind=kind):
                payload = (kind + "-full-content").encode()
                digest = self.digest(payload)
                destination = self.store.root / digest
                observed = []

                def publishing(temporary, target):
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        observed.append(
                            pool.submit(self.store.has, digest).result(timeout=5)
                        )
                    return original_replace(temporary, target)

                with patch.object(Path, "replace", publishing):
                    if kind == "upload":
                        self.store.put(digest, len(payload), 0, payload)
                    else:
                        source = self.store.root / "native-import-source"
                        source.write_bytes(payload)
                        self.store.import_file(source, digest, len(payload))
                self.assertEqual(observed, [False])
                self.assertEqual(destination.read_bytes(), payload)
                self.assertTrue(self.store.has(digest, len(payload)))
                self.assertEqual(self.store.read(digest), payload)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = ContextStore(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def digest(data):
        return hashlib.sha256(data).hexdigest()

    def put_chunks(self, data, chunk_size=128 * 1024, digest=None):
        digest = digest or self.digest(data)
        offsets = []
        for offset in range(0, len(data), chunk_size):
            block = data[offset : offset + chunk_size]
            result = self.store.put(digest, len(data), offset, block)
            offsets.append(result["offset"])
        if not data:
            result = self.store.put(digest, 0, 0, b"")
            offsets.append(result["offset"])
        return digest, offsets

    def store_manifest(self, entries):
        data = json.dumps(
            {"format": "wakfu-complete-context-1", "entries": entries},
            separators=(",", ":"),
        ).encode()
        digest, _ = self.put_chunks(data, chunk_size=97)
        return digest

    def test_blob_larger_than_transport_frame_is_reassembled_without_truncation(self):
        payload = bytes(range(251)) * 12000  # ~2.9 MiB; individual frames stay small.
        digest, offsets = self.put_chunks(payload, chunk_size=64 * 1024)
        self.assertGreater(len(offsets), 40)
        self.assertTrue(self.store.has(digest, len(payload)))
        self.assertEqual(self.store.read(digest), payload)
        self.assertEqual(
            self.store.put(digest, len(payload), 0, payload[:100]),
            {"complete": True, "offset": len(payload)},
        )

    def test_retries_are_idempotent_and_conflicting_or_out_of_order_chunks_fail(self):
        payload = b"abcdefghij"
        digest = self.digest(payload)
        first = self.store.put(digest, len(payload), 0, b"abcd")
        self.assertEqual(first, {"complete": False, "offset": 4})
        self.assertEqual(self.store.put(digest, len(payload), 0, b"abcd"), first)
        with self.assertRaisesRegex(ValueError, "Conflicting repeated context block"):
            self.store.put(digest, len(payload), 0, b"xxxx")
        with self.assertRaisesRegex(ValueError, "Out-of-order context block"):
            self.store.put(digest, len(payload), 8, b"ij")
        with self.assertRaisesRegex(ValueError, "Context object size changed"):
            self.store.put(digest, len(payload) + 1, 4, b"ef")
        self.assertEqual(
            self.store.put(digest, len(payload), 4, b"efghij"),
            {"complete": True, "offset": len(payload)},
        )
        self.assertEqual(
            self.store.put(digest, len(payload), 0, payload),
            {"complete": True, "offset": len(payload)},
        )
        self.assertEqual(self.store.read(digest), payload)

    def test_incomplete_upload_and_wrong_content_hash_never_become_verified(self):
        payload = b"intended bytes"
        digest = self.digest(payload)
        result = self.store.put(digest, len(payload), 0, b"wrong")
        self.assertEqual(result, {"complete": False, "offset": 5})
        with self.assertRaisesRegex(ValueError, "Context content checksum mismatch"):
            self.store.put(digest, len(payload), 5, b"x" * (len(payload) - 5))
        self.assertFalse(self.store.has(digest))
        self.assertFalse((Path(self.temporary.name) / (digest + ".partial")).exists())
        with self.assertRaisesRegex(ValueError, "Context content checksum mismatch"):
            self.store.put(digest, len(payload), 0, b"wrong contents")

        other = b"unfinished upload"
        other_hash = self.digest(other)
        self.store.put(other_hash, len(other), 0, other[:4])
        self.assertFalse(self.store.has(other_hash, len(other)))
        with self.assertRaisesRegex(ValueError, "Missing verified context content"):
            self.store.read(other_hash)

    def test_manifest_waits_for_every_full_verified_entry_and_lists_all(self):
        entries = []
        for index in range(70):
            payload = f"catalog-entry-{index:03d}:".encode() + bytes([index]) * 37
            digest, _ = self.put_chunks(payload, chunk_size=11)
            entries.append(
                {
                    "path": f"catalog/section-{index // 10}/entry-{index}.bin",
                    "sha256": digest,
                    "size": len(payload),
                }
            )
        large_catalog = b"catalog-data:" + b"x" * (2 * 1024 * 1024)
        catalog_hash, _ = self.put_chunks(large_catalog, chunk_size=128 * 1024)
        entries.append(
            {
                "path": "catalog/complete.bin",
                "sha256": catalog_hash,
                "size": len(large_catalog),
            }
        )

        manifest_hash = self.store_manifest(entries)
        result = self.store.manifest(manifest_hash)
        self.assertEqual(result, {"complete": True, "missing": [], "entries": 71})

    def test_missing_entry_blocks_completion_until_uploaded(self):
        missing = b"native asset not received yet"
        missing_hash = self.digest(missing)
        manifest_hash = self.store_manifest(
            [
                {
                    "path": "assets/native.bin",
                    "sha256": missing_hash,
                    "size": len(missing),
                }
            ]
        )
        self.assertEqual(
            self.store.manifest(manifest_hash),
            {"complete": False, "missing": [missing_hash], "entries": 1},
        )
        self.put_chunks(missing, chunk_size=7)
        self.assertEqual(
            self.store.manifest(manifest_hash),
            {"complete": True, "missing": [], "entries": 1},
        )

    def test_manifest_checks_shared_blob_once_per_validation_and_rechecks_next_time(
        self,
    ):
        payload = b"same complete native bytes"
        digest, _ = self.put_chunks(payload)
        entries = [
            {"path": name, "sha256": digest, "size": len(payload)}
            for name in ("catalog/full.bin", "server/protocol/full.bin")
        ]
        manifest = self.store_manifest(entries)
        with patch.object(self.store, "has", wraps=self.store.has) as has:
            self.assertTrue(self.store.manifest(manifest)["complete"])
            self.assertEqual(
                sum(call.args[0] == digest for call in has.call_args_list), 1
            )
            self.store._path(digest).write_bytes(b"x" * len(payload))
            result = self.store.manifest(manifest)
            self.assertEqual(
                result, {"complete": False, "missing": [digest], "entries": 2}
            )
            self.assertEqual(
                sum(call.args[0] == digest for call in has.call_args_list), 2
            )
        entries[1]["size"] += 1
        with self.assertRaisesRegex(
            ValueError, "Conflicting complete context object sizes"
        ):
            self.store.manifest(self.store_manifest(entries))

    def test_corrupt_blob_cannot_satisfy_a_previously_verified_manifest(self):
        payload = b"verified source data"
        digest, _ = self.put_chunks(payload)
        manifest_hash = self.store_manifest(
            [{"path": "snapshot/state.bin", "sha256": digest, "size": len(payload)}]
        )
        self.assertTrue(self.store.manifest(manifest_hash)["complete"])

        # Model on-disk corruption after an earlier successful read/verification.
        (Path(self.temporary.name) / digest).write_bytes(b"x" * len(payload))
        self.assertFalse(self.store.has(digest, len(payload)))
        self.assertFalse(self.store.manifest(manifest_hash)["complete"])

    def test_corrupt_gzip_context_is_rejected_after_compressed_hash_verifies(self):
        compressed = gzip.compress(
            b'{"complete":"native graph"}', compresslevel=1, mtime=0
        )
        corrupted = compressed[:-3]
        digest, _ = self.put_chunks(corrupted, chunk_size=7)
        self.assertTrue(self.store.has(digest, len(corrupted)))
        self.assertEqual(self.store.read(digest), corrupted)
        with self.assertRaisesRegex(ValueError, "Invalid compressed complete context"):
            self.store.json(digest)

    def test_invalid_manifest_paths_hashes_and_duplicate_entries_rejected(self):
        valid_data = b"ok"
        valid_hash, _ = self.put_chunks(valid_data)
        malformed_entries = [
            [{"path": "../escape", "sha256": valid_hash, "size": 2}],
            [{"path": "/absolute", "sha256": valid_hash, "size": 2}],
            [{"path": "a\\b", "sha256": valid_hash, "size": 2}],
            [
                {"path": "same", "sha256": valid_hash, "size": 2},
                {"path": "same", "sha256": valid_hash, "size": 2},
            ],
            [{"path": "bad-hash", "sha256": "not-a-hash", "size": 2}],
        ]
        for entries in malformed_entries:
            with self.subTest(entries=entries):
                manifest_hash = self.store_manifest(entries)
                with self.assertRaises(ValueError):
                    self.store.manifest(manifest_hash)


if __name__ == "__main__":
    unittest.main()
