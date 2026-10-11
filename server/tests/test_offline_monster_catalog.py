"""Offline declared releases never bypass per-read SHA authority."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from offline_monster_catalog import OfflineMonsterCatalog


class OfflineMonsterCatalogTests(unittest.TestCase):
    def fixture(self, path):
        candidate = path / "candidate"
        candidate.mkdir()
        raw = b'{"rows":{"1":{"value":7}}}'
        (candidate / "base-proof.json").write_bytes(raw)
        (candidate / "manifest.json").write_text(
            json.dumps(
                dict(
                    schema="native-npc-activation-candidate-v1",
                    base_revision="offline-test",
                    unchanged_documents={},
                    base_document_hashes={
                        "proof.json": hashlib.sha256(raw).hexdigest()
                    },
                )
            )
        )
        return candidate

    def test_verified_read_record_and_declared_offline_receipt(self):
        from wakfu_server import native_catalog

        with tempfile.TemporaryDirectory() as directory:
            snapshot = OfflineMonsterCatalog(self.fixture(Path(directory)))
            with snapshot.install():
                self.assertEqual(native_catalog.release(), "offline-test")
                self.assertEqual(
                    native_catalog.record(
                        native_catalog.DATA_ROOT / "proof.json", "rows", 1
                    ),
                    {"value": 7},
                )
            receipt = snapshot.receipt()
            self.assertEqual(receipt["declared_document_count"], 1)
            self.assertEqual(set(receipt["verified_documents"]), {"proof.json"})
            self.assertIn("not_active_database", receipt["authority"])

    def test_mutated_raw_rejects_instead_of_trusting_manifest(self):
        from wakfu_server import native_catalog

        with tempfile.TemporaryDirectory() as directory:
            candidate = self.fixture(Path(directory))
            snapshot = OfflineMonsterCatalog(candidate)
            (candidate / "base-proof.json").write_text("{}")
            with snapshot.install(), self.assertRaisesRegex(
                FileNotFoundError, "SHA-qualified"
            ):
                native_catalog.load(native_catalog.DATA_ROOT / "proof.json")
            self.assertEqual(snapshot.receipt()["verified_documents"], {})
            self.assertEqual(len(snapshot.receipt()["failed_reads"]), 1)

    def test_undeclared_document_cannot_be_loaded_from_root(self):
        from wakfu_server import native_catalog

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = self.fixture(root)
            (root / "unknown.json").write_text("{}")
            with OfflineMonsterCatalog(
                candidate, [root]
            ).install(), self.assertRaisesRegex(FileNotFoundError, "Undeclared"):
                native_catalog.load(native_catalog.DATA_ROOT / "unknown.json")

    def test_exists_and_open_are_sealed_offline_reads_without_database(self):
        from wakfu_server import native_catalog
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            snapshot = OfflineMonsterCatalog(self.fixture(Path(directory)))
            with snapshot.install(), patch.object(
                native_catalog, "_database", side_effect=AssertionError("DB forbidden")
            ):
                self.assertTrue(
                    native_catalog.exists(native_catalog.DATA_ROOT / "proof.json")
                )
                self.assertFalse(
                    native_catalog.exists(native_catalog.DATA_ROOT / "unknown.json")
                )
                with native_catalog.open(
                    native_catalog.DATA_ROOT / "proof.json", "rb"
                ) as stream:
                    self.assertEqual(json.load(stream), {"rows": {"1": {"value": 7}}})
            self.assertEqual(
                set(snapshot.receipt()["verified_documents"]), {"proof.json"}
            )

    def test_gzip_source_is_qualified_by_decompressed_manifest_bytes(self):
        import gzip
        from wakfu_server import native_catalog

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = self.fixture(root)
            raw = (candidate / "base-proof.json").read_bytes()
            (candidate / "base-proof.json").unlink()
            (root / "proof.json.gz").write_bytes(gzip.compress(raw))
            snapshot = OfflineMonsterCatalog(candidate, [root])
            with snapshot.install():
                self.assertEqual(
                    native_catalog.read_bytes(native_catalog.DATA_ROOT / "proof.json"),
                    raw,
                )
            self.assertTrue(
                snapshot.receipt()["verified_documents"]["proof.json"]["gzip"]
            )
