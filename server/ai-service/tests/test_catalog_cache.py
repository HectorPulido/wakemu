"""Persistent preparation preserves a freshly enumerated complete catalogue."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from wakfu_ai.bridge.world_bridge import CompleteContextExporter


class CatalogCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "sources"
        self.root.mkdir()
        self.source = self.root / "future.opaque"
        self.source.write_bytes(b"complete-source" * 4096)
        self.cache = Path(self.temporary.name) / "private-cache"

    def exporter(self):
        result = CompleteContextExporter({"all": self.root}, cache_root=self.cache)
        self.addCleanup(result.close)
        return result

    def test_next_process_reuses_verified_bytes_without_reading_source_again(self):
        first = self.exporter()
        manifest, sources = first.inventory()
        first.close()
        second = self.exporter()
        original = Path.open
        reads = []

        def opened(path, *args, **kwargs):
            if path == self.source:
                reads.append(path)
            return original(path, *args, **kwargs)

        with patch.object(Path, "open", opened):
            again, new_sources = second.inventory()
        self.assertEqual(reads, [])
        self.assertEqual(again, manifest)
        self.assertEqual(new_sources, sources)
        digest = manifest["entries"][0]["sha256"]
        self.assertEqual(
            hashlib.sha256(new_sources[digest].read_bytes()).hexdigest(), digest
        )

    def test_changed_source_with_preserved_mtime_is_recaptured_and_new_files_enumerated(
        self,
    ):
        first = self.exporter()
        previous, _ = first.inventory()
        status = self.source.stat()
        self.source.write_bytes(b"replacement!!!" * 4096)
        os.utime(self.source, ns=(status.st_atime_ns, status.st_mtime_ns))
        future = self.root / ".future-extension"
        future.write_bytes(b"all-new-fields")
        current, sources = self.exporter().inventory()
        self.assertEqual(len(current["entries"]), 2)
        changed = next(
            row for row in current["entries"] if row["path"].endswith("future.opaque")
        )
        self.assertNotEqual(changed["sha256"], previous["entries"][0]["sha256"])
        self.assertEqual(
            sources[changed["sha256"]].read_bytes(), self.source.read_bytes()
        )

    def test_corrupt_snapshot_is_repaired_both_after_restore_and_with_live_exporter(
        self,
    ):
        first = self.exporter()
        manifest, sources = first.inventory()
        digest = manifest["entries"][0]["sha256"]
        sources[digest].write_bytes(b"x" * self.source.stat().st_size)
        restored = self.exporter()
        current, repaired = restored.inventory()
        self.assertEqual(current, manifest)
        self.assertEqual(repaired[digest].read_bytes(), self.source.read_bytes())
        repaired[digest].write_bytes(b"y" * self.source.stat().st_size)
        _, repaired = restored.inventory()
        self.assertEqual(repaired[digest].read_bytes(), self.source.read_bytes())

    def test_invalid_index_is_only_a_cache_miss_and_never_omits_sources(self):
        first = self.exporter()
        expected, _ = first.inventory()
        for invalid in (
            b"invalid JSON",
            b"{}",
            json.dumps(
                [
                    {
                        "key": [True, 1],
                        "signature": [1, 2, 3, 4, 5],
                        "sha256": "a" * 64,
                        "snapshotIdentity": [1, 2, 3, 4, 5],
                    }
                ]
            ).encode(),
        ):
            first._cache_index.write_bytes(invalid)
            actual, sources = self.exporter().inventory()
            self.assertEqual(actual, expected)
            self.assertEqual(len(sources), 1)

    def test_root_aliases_keep_all_entries_and_removed_files_do_not_survive_manifest(
        self,
    ):
        exporter = CompleteContextExporter(
            {"all": self.root, "alias": self.root}, cache_root=self.cache
        )
        self.addCleanup(exporter.close)
        manifest, sources = exporter.inventory()
        self.assertEqual(len(manifest["entries"]), 2)
        self.assertEqual(len(sources), 1)
        self.source.unlink()
        again, sources = exporter.inventory()
        self.assertEqual(again["entries"], [])
        self.assertEqual(sources, {})
