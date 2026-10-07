"""Private immutable catalogue snapshots, independent of mutable CAS blobs."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from wakfu_ai.context.context_store import ContextStore


class ContextSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ContextStore(self.tmp.name)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    @staticmethod
    def digest(data):
        return hashlib.sha256(data).hexdigest()

    def put(self, data):
        digest = self.digest(data)
        self.store.put(digest, len(data), 0, data)
        return digest

    def manifest(self, entries):
        data = json.dumps(
            dict(format="wakfu-complete-context-1", entries=entries),
            separators=(",", ":"),
        ).encode()
        return self.put(data)

    def test_seal_preserves_aliases_unknown_extensions_and_full_bytes(self):
        payload = bytes(range(256)) * 4096
        digest = self.put(payload)
        entries = [
            dict(path=name, sha256=digest, size=len(payload))
            for name in (
                "catalog/future/extension.bin",
                "server/protocol/catalog-copy.opaque",
            )
        ]
        manifest = self.manifest(entries)
        self.assertEqual(
            self.store.seal_manifest(manifest),
            dict(complete=True, missing=[], entries=2),
        )
        self.assertEqual(self.store.read_catalog(manifest, digest), payload)
        raw_manifest = self.store.read(manifest)
        self.assertEqual(self.store.read_catalog(manifest, manifest), raw_manifest)
        self.assertEqual(self.store.json(manifest)["entries"], entries)

    def test_missing_blob_resumes_and_no_partial_snapshot_is_published(self):
        payload = b"upload after an incomplete seal"
        digest = self.digest(payload)
        manifest = self.manifest(
            [dict(path="assets/new.bin", sha256=digest, size=len(payload))]
        )
        result = self.store.seal_manifest(manifest)
        self.assertEqual(result, dict(complete=False, missing=[digest], entries=1))
        with self.assertRaisesRegex(ValueError, "not been sealed"):
            self.store.read_catalog(manifest, digest)
        self.store.put(digest, len(payload), 0, payload)
        self.assertEqual(
            self.store.seal_manifest(manifest),
            dict(complete=True, missing=[], entries=1),
        )
        self.assertEqual(self.store.read_catalog(manifest, digest), payload)

    def test_invalid_size_hash_pair_is_rejected_before_snapshot_publication(self):
        payload = b"same digest cannot claim a different size"
        digest = self.put(payload)
        manifest = self.manifest(
            [
                dict(path="a.bin", sha256=digest, size=len(payload)),
                dict(path="b.bin", sha256=digest, size=len(payload) + 1),
            ]
        )
        with self.assertRaisesRegex(
            ValueError, "Conflicting complete context object sizes"
        ):
            self.store.seal_manifest(manifest)
        self.assertFalse(any(Path(self.store._snapshot_dir).glob("*.catalog")))

    def test_source_mutation_during_capture_rejects_and_cleans_temporary_copy(self):
        payload = b"source that changes in the middle"
        digest = self.put(payload)
        manifest = self.manifest(
            [dict(path="source.bin", sha256=digest, size=len(payload))]
        )
        path = self.store._path(digest)
        original_stat = Path.stat
        calls = 0

        def mutating_stat(target, *args, **kwargs):
            nonlocal calls
            if target == path:
                calls += 1
                if calls == 2:
                    path.write_bytes(b"z" * len(payload))
            return original_stat(target, *args, **kwargs)

        with patch.object(Path, "stat", mutating_stat):
            with self.assertRaisesRegex(ValueError, "changed while sealing"):
                self.store.seal_manifest(manifest)
        self.assertFalse(any(Path(self.store._snapshot_dir).iterdir()))

    def test_snapshot_io_failure_closes_and_removes_unpublished_temporary_file(self):
        payload = b"copy failure"
        digest = self.put(payload)
        manifest = self.manifest([dict(path="asset", sha256=digest, size=len(payload))])
        with patch(
            "wakfu_ai.context.context_store.os.fsync",
            side_effect=OSError("disk sync failed"),
        ):
            with self.assertRaisesRegex(OSError, "disk sync failed"):
                self.store.seal_manifest(manifest)
        self.assertEqual(list(Path(self.store._snapshot_dir).iterdir()), [])
        # A failed capture releases the per-version reservation and is retryable.
        self.assertTrue(self.store.seal_manifest(manifest)["complete"])

    def test_delta_publication_failure_leaves_no_refs_or_files_and_can_retry(self):
        payload = b"new archive object"
        digest = self.put(payload)
        manifest = self.manifest(
            [dict(path="future.ext", sha256=digest, size=len(payload))]
        )
        with patch(
            "wakfu_ai.context.context_store.os.replace",
            side_effect=OSError("publish failed"),
        ):
            with self.assertRaisesRegex(OSError, "publish failed"):
                self.store.seal_manifest(manifest)
        self.assertEqual(list(Path(self.store._snapshot_dir).iterdir()), [])
        self.assertNotIn(digest, self.store._blob_refs)
        self.assertNotIn(manifest, self.store._sealed)
        self.assertTrue(self.store.seal_manifest(manifest)["complete"])

    def test_canonical_corruption_or_replacement_does_not_change_sealed_bytes(self):
        original = b"immutable snapshot content"
        digest = self.put(original)
        manifest = self.manifest(
            [dict(path="future.bin", sha256=digest, size=len(original))]
        )
        self.assertTrue(self.store.seal_manifest(manifest)["complete"])
        path = self.store._path(digest)
        path.write_bytes(b"x" * len(original))
        self.assertFalse(self.store.has(digest))
        self.assertFalse(self.store.manifest(manifest)["complete"])
        self.assertEqual(self.store.read_catalog(manifest, digest), original)
        path.unlink()
        self.assertEqual(self.store.read_catalog(manifest, digest), original)

    def test_private_archive_same_size_mutation_and_replacement_are_rejected(self):
        payload = b"private immutable archive bytes"
        digest = self.put(payload)
        manifest = self.manifest([dict(path="asset", sha256=digest, size=len(payload))])
        self.assertTrue(self.store.seal_manifest(manifest)["complete"])
        archive = Path(
            self.store._sealed[manifest]["snapshot"]["blobs"][digest]["path"]
        )
        self.assertEqual(self.store.read_catalog(manifest, digest), payload)

        original_stat = archive.stat()
        archive.chmod(0o600)
        archive.write_bytes(b"z" * original_stat.st_size)
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            self.store.read_catalog(manifest, digest)
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            self.store.seal_manifest(manifest)
        second = self.manifest(
            [
                dict(path="asset", sha256=digest, size=len(payload)),
                dict(path="alias", sha256=digest, size=len(payload)),
            ]
        )
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            self.store.seal_manifest(second)

        # Replacement detection is isolated from the corrupted archive above.
        replacement_store = ContextStore(Path(self.tmp.name) / "replacement")
        replacement_payload = b"replacement inode bytes"
        replacement_digest = hashlib.sha256(replacement_payload).hexdigest()
        replacement_store.put(
            replacement_digest, len(replacement_payload), 0, replacement_payload
        )
        replacement_manifest_bytes = json.dumps(
            dict(
                format="wakfu-complete-context-1",
                entries=[
                    dict(
                        path="asset",
                        sha256=replacement_digest,
                        size=len(replacement_payload),
                    )
                ],
            ),
            separators=(",", ":"),
        ).encode()
        replacement_manifest = hashlib.sha256(replacement_manifest_bytes).hexdigest()
        replacement_store.put(
            replacement_manifest,
            len(replacement_manifest_bytes),
            0,
            replacement_manifest_bytes,
        )
        self.assertTrue(
            replacement_store.seal_manifest(replacement_manifest)["complete"]
        )
        second_archive = Path(
            replacement_store._sealed[replacement_manifest]["snapshot"]["blobs"][
                replacement_digest
            ]["path"]
        )
        self.assertEqual(
            replacement_store.read_catalog(replacement_manifest, replacement_digest),
            replacement_payload,
        )
        replacement = second_archive.with_suffix(".replacement")
        replacement.write_bytes(second_archive.read_bytes())
        replacement.chmod(0o400)
        replacement.replace(second_archive)
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            replacement_store.read_catalog(replacement_manifest, replacement_digest)
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            replacement_store.seal_manifest(replacement_manifest)
        replacement_store.close()

    def test_seal_identity_checks_once_per_unique_archive_not_once_per_blob(self):
        rows = []
        for index in range(40):
            payload = f"frozen-object-{index}".encode()
            digest = self.put(payload)
            rows.append(
                dict(path=f"assets/{index}.future", sha256=digest, size=len(payload))
            )
        manifest = self.manifest(rows)
        self.assertTrue(self.store.seal_manifest(manifest)["complete"])
        first_refs = self.store._sealed[manifest]["snapshot"]["blobs"]
        archive = Path(next(iter(first_refs.values()))["path"])
        self.assertEqual({ref["path"] for ref in first_refs.values()}, {str(archive)})

        original_stat = Path.stat
        count = 0

        def counted_stat(path, *args, **kwargs):
            nonlocal count
            if path == archive:
                count += 1
            return original_stat(path, *args, **kwargs)

        with patch.object(Path, "stat", counted_stat):
            self.assertTrue(self.store.seal_manifest(manifest)["complete"])
        self.assertEqual(count, 1)

        new_payload = b"new archive delta"
        new_digest = self.put(new_payload)
        second_manifest = self.manifest(
            rows
            + [dict(path="assets/new.future", sha256=new_digest, size=len(new_payload))]
        )
        count = 0
        with patch.object(Path, "stat", counted_stat):
            self.assertTrue(self.store.seal_manifest(second_manifest)["complete"])
        # One check before delta construction and one immediately before the
        # second manifest becomes visible, despite forty references to archive.
        self.assertEqual(count, 2)

    def test_new_manifest_reuses_large_frozen_blob_and_archives_only_new_bytes(self):
        large = b"a" * (2 * 1024 * 1024)
        large_digest = self.put(large)
        first_manifest = self.manifest(
            [
                dict(
                    path="catalog/alias-one.future",
                    sha256=large_digest,
                    size=len(large),
                ),
                dict(
                    path="server/protocol/alias-two.opaque",
                    sha256=large_digest,
                    size=len(large),
                ),
            ]
        )
        self.assertTrue(self.store.seal_manifest(first_manifest)["complete"])
        first_ref = self.store._sealed[first_manifest]["snapshot"]["blobs"][
            large_digest
        ]

        # The canonical source may disappear after its bytes have been frozen.
        self.store._path(large_digest).unlink()
        small = b"new future extension"
        small_digest = self.put(small)
        second_manifest = self.manifest(
            [
                dict(
                    path="catalog/alias-one.future",
                    sha256=large_digest,
                    size=len(large),
                ),
                dict(
                    path="catalog/alias-two.future",
                    sha256=large_digest,
                    size=len(large),
                ),
                dict(
                    path="native/new-extension.zzz",
                    sha256=small_digest,
                    size=len(small),
                ),
            ]
        )
        self.assertTrue(self.store.seal_manifest(second_manifest)["complete"])
        second_blobs = self.store._sealed[second_manifest]["snapshot"]["blobs"]
        second_ref = second_blobs[large_digest]
        delta_path = Path(second_blobs[small_digest]["path"])
        self.assertEqual(first_ref, second_ref)
        self.assertEqual(
            delta_path.stat().st_size,
            len(small) + len(self.store.read(second_manifest)),
        )
        self.assertLess(delta_path.stat().st_size, len(large))
        self.assertEqual(self.store.read_catalog(first_manifest, large_digest), large)
        self.assertEqual(self.store.read_catalog(second_manifest, large_digest), large)
        self.assertEqual(self.store.read_catalog(second_manifest, small_digest), small)
        self.assertFalse(self.store.has(large_digest))
        self.assertEqual(
            self.store.manifest(second_manifest),
            dict(complete=False, missing=[large_digest], entries=3),
        )

    def test_concurrent_manifests_copy_shared_new_blobs_once_without_order_deadlock(
        self,
    ):
        first_payload, second_payload = b"first shared blob", b"second shared blob"
        first_hash, second_hash = self.put(first_payload), self.put(second_payload)
        manifest_a = self.manifest(
            [
                dict(path="a/first", sha256=first_hash, size=len(first_payload)),
                dict(path="a/second", sha256=second_hash, size=len(second_payload)),
            ]
        )
        manifest_b = self.manifest(
            [
                dict(path="b/second", sha256=second_hash, size=len(second_payload)),
                dict(path="b/first", sha256=first_hash, size=len(first_payload)),
            ]
        )
        original_open = Path.open
        copied, copied_lock = [], threading.Lock()
        started, release = threading.Event(), threading.Event()

        def counted_open(path, *args, **kwargs):
            if path in (self.store._path(first_hash), self.store._path(second_hash)):
                with copied_lock:
                    copied.append(path.name)
                started.set()
                if not release.wait(2):
                    raise AssertionError("shared blob copy was not released")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", counted_open):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.store.seal_manifest, manifest_a)
                self.assertTrue(started.wait(2))
                second = pool.submit(self.store.seal_manifest, manifest_b)
                release.set()
                replies = [first.result(timeout=4), second.result(timeout=4)]
        self.assertEqual(replies, [dict(complete=True, missing=[], entries=2)] * 2)
        self.assertEqual(sorted(copied), sorted([first_hash, second_hash]))
        for manifest in (manifest_a, manifest_b):
            self.assertEqual(
                self.store.read_catalog(manifest, first_hash), first_payload
            )
            self.assertEqual(
                self.store.read_catalog(manifest, second_hash), second_payload
            )

    def test_distinct_manifest_seals_do_not_hold_a_global_heavy_lock(self):
        payload = b"shared asset"
        asset = self.put(payload)
        manifests = [
            self.manifest([dict(path=f"v{i}/x", sha256=asset, size=len(payload))])
            for i in range(2)
        ]
        barrier = threading.Barrier(2)
        capture = self.store._capture_manifest

        def synchronized(digest):
            barrier.wait(timeout=3)
            return capture(digest)

        with patch.object(self.store, "_capture_manifest", side_effect=synchronized):
            with ThreadPoolExecutor(max_workers=2) as pool:
                replies = list(pool.map(self.store.seal_manifest, manifests))
        self.assertEqual(replies, [dict(complete=True, missing=[], entries=1)] * 2)

    def test_same_manifest_concurrent_seal_is_single_capture(self):
        payload = b"one version"
        digest = self.put(payload)
        manifest = self.manifest(
            [dict(path="future.one", sha256=digest, size=len(payload))]
        )
        capture = self.store._capture_manifest
        entered, release = threading.Event(), threading.Event()
        calls = []

        def slow_capture(value):
            calls.append(value)
            entered.set()
            if not release.wait(3):
                raise AssertionError("capture was not released")
            return capture(value)

        with patch.object(self.store, "_capture_manifest", side_effect=slow_capture):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.store.seal_manifest, manifest)
                self.assertTrue(entered.wait(2))
                second = pool.submit(self.store.seal_manifest, manifest)
                release.set()
                futures = [first, second]
                replies = [future.result(timeout=5) for future in futures]
        self.assertEqual(len(calls), 1)
        self.assertEqual(replies, [dict(complete=True, missing=[], entries=1)] * 2)

    def test_close_removes_private_snapshot_files(self):
        digest = self.put(b"x")
        manifest = self.manifest([dict(path="x", sha256=digest, size=1)])
        self.store.seal_manifest(manifest)
        snapshot_dir = Path(self.store._snapshot_dir)
        self.assertTrue(snapshot_dir.exists())
        self.store.close()
        self.assertFalse(snapshot_dir.exists())


if __name__ == "__main__":
    unittest.main()
