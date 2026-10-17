"""Offline catalog capture/replay contract regressions."""
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import sys
import types
import unittest
from unittest.mock import patch, MagicMock

from wakfu_server import native_catalog
from wakfu_server.combat_reproduction_catalog import (
    CaptureCatalog,
    MissingReproductionCatalog,
    ReplayCatalog,
)


class CatalogReproductionTests(unittest.TestCase):
    def make_bundle(self, directory):
        raw = b'{"spells":{"42":{"id":42}}}'
        digest = hashlib.sha256(raw).hexdigest()
        database = MagicMock()
        database.connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = {
            "raw": raw,
            "sha256": digest,
        }
        path = native_catalog.DATA_ROOT / "example.json"
        with patch.object(
            native_catalog, "release", return_value="release-1"
        ), patch.object(
            native_catalog, "document_hashes", return_value={"example.json": digest}
        ), patch.object(
            native_catalog, "load", return_value=json.loads(raw)
        ), patch.object(
            native_catalog, "record", return_value={"id": 42}
        ), patch.object(
            native_catalog,
            "exists",
            side_effect=lambda value: Path(value).name == "example.json",
        ), patch.object(
            native_catalog, "_database", return_value=database
        ):
            with CaptureCatalog() as capture:
                self.assertEqual(native_catalog.load(path)["spells"]["42"]["id"], 42)
                self.assertEqual(native_catalog.record(path, "spells", 42), {"id": 42})
                self.assertFalse(
                    native_catalog.exists(native_catalog.DATA_ROOT / "absent.json")
                )
                capture.export(directory)
        return path, raw, digest

    def test_capture_replay_is_offline_and_restores_functions(self):
        with tempfile.TemporaryDirectory() as directory:
            path, raw, _ = self.make_bundle(directory)
            original = native_catalog.load
            with patch.object(
                native_catalog, "_database", side_effect=AssertionError("SQL in replay")
            ), patch.object(
                native_catalog, "_redis", side_effect=AssertionError("Redis in replay")
            ):
                with ReplayCatalog(directory).install():
                    self.assertEqual(native_catalog.release(), "release-1")
                    self.assertEqual(native_catalog.read_bytes(path), raw)
                    self.assertEqual(
                        native_catalog.record(path, "spells", 42), {"id": 42}
                    )
                    self.assertFalse(
                        native_catalog.exists(native_catalog.DATA_ROOT / "absent.json")
                    )
                    with native_catalog.open(path, "rb") as source:
                        self.assertEqual(source.read(), raw)
                    with self.assertRaises(FileNotFoundError):
                        native_catalog.record(path, "spells", 43)
                    with self.assertRaises(FileNotFoundError):
                        native_catalog.load(native_catalog.DATA_ROOT / "other.json")
                    with self.assertRaises(FileNotFoundError):
                        native_catalog.exists(native_catalog.DATA_ROOT / "other.json")
                    with self.assertRaises(ValueError):
                        native_catalog.read_bytes("/etc/passwd")
            self.assertIs(native_catalog.load, original)

    def test_tampered_and_missing_blobs_are_rejected(self):
        for mode in ("tamper", "missing"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                _, raw, digest = self.make_bundle(directory)
                blob = Path(directory) / "catalog" / digest
                if mode == "tamper":
                    blob.write_bytes(b"x" * len(raw))
                else:
                    blob.unlink()
                with self.assertRaises((ValueError, FileNotFoundError)):
                    ReplayCatalog(directory)

    def test_manifest_provenance_paths_and_bounds(self):
        mutations = (
            lambda value: value.update(version=99),
            lambda value: value.update(authority="files"),
            lambda value: value["published_hashes"].update({"../escape": "a" * 64}),
            lambda value: value["documents"]["example.json"].update(size=-1),
            lambda value: value["documents"]["example.json"].update(sha256="../escape"),
            lambda value: value["exists"].update({"absent.json": True}),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                self.make_bundle(directory)
                path = Path(directory) / "catalog.json"
                value = json.loads(path.read_bytes())
                mutate(value)
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    ReplayCatalog(directory)

    def test_container_origin_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            _, raw, _ = self.make_bundle(directory)
            path = Path(directory) / "catalog.json"
            value = json.loads(path.read_bytes())
            value["data_root"] = "/app/server/protocol"
            path.write_text(json.dumps(value))
            replay = ReplayCatalog(directory)
            self.assertEqual(
                replay.read_bytes("/app/server/protocol/example.json"), raw
            )
            with self.assertRaises(ValueError):
                replay.read_bytes("/app/server/protocol/../secret.json")

    def test_direct_aliases_imported_inside_context_are_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _ = self.make_bundle(directory)
            alias_module = types.ModuleType("_catalog_replay_alias_test")
            sys.modules[alias_module.__name__] = alias_module
            original = native_catalog.read_bytes
            try:
                with ReplayCatalog(directory).install():
                    alias_module.read = native_catalog.read_bytes
                    self.assertEqual(
                        json.loads(alias_module.read(path))["spells"]["42"]["id"], 42
                    )
                self.assertIs(alias_module.read, original)
            finally:
                sys.modules.pop(alias_module.__name__, None)

    def test_blob_symlink_cannot_escape_bundle(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            _, raw, digest = self.make_bundle(directory)
            external = Path(outside) / digest
            external.write_bytes(raw)
            blob = Path(directory) / "catalog" / digest
            blob.unlink()
            blob.symlink_to(external)
            with self.assertRaises(ValueError):
                ReplayCatalog(directory)

    def test_explicit_storage_import_after_install_is_offline_and_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            path, raw, _ = self.make_bundle(directory)
            parent = importlib.import_module("wakfu_server.storage")
            name = "wakfu_server.storage.native_catalog"
            saved_module = sys.modules.pop(name, None)
            saved_attribute = parent.__dict__.pop("native_catalog", None)
            try:
                with patch.object(
                    native_catalog, "_database", side_effect=AssertionError("SQL")
                ), patch.object(
                    native_catalog, "_redis", side_effect=AssertionError("Redis")
                ), patch.object(
                    native_catalog,
                    "read_bytes",
                    side_effect=AssertionError("Original read"),
                ):
                    with ReplayCatalog(directory).install():
                        explicit = importlib.import_module(name)
                        from wakfu_server.storage import native_catalog as via_parent

                        self.assertIs(explicit, native_catalog)
                        self.assertIs(via_parent, native_catalog)
                        self.assertEqual(explicit.read_bytes(path), raw)
                        with self.assertRaises(MissingReproductionCatalog):
                            explicit.load(native_catalog.DATA_ROOT / "unknown.json")
                    self.assertNotIn(name, sys.modules)
                    self.assertNotIn("native_catalog", parent.__dict__)
            finally:
                if saved_module is not None:
                    sys.modules[name] = saved_module
                if saved_attribute is not None:
                    parent.native_catalog = saved_attribute

    def test_preloaded_storage_duplicate_and_aliases_restore_with_nested_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            path, raw, _ = self.make_bundle(directory)
            parent = importlib.import_module("wakfu_server.storage")
            name = "wakfu_server.storage.native_catalog"
            saved_module = sys.modules.pop(name, None)
            saved_attribute = parent.__dict__.pop("native_catalog", None)
            aliases = types.ModuleType("_duplicate_catalog_alias_test")
            sys.modules[aliases.__name__] = aliases
            try:
                duplicate = importlib.import_module(name)
                self.assertIsNot(duplicate, native_catalog)
                original_load = duplicate.load
                aliases.load = duplicate.load
                with patch.object(
                    duplicate, "_database", side_effect=AssertionError("Duplicate SQL")
                ), patch.object(
                    duplicate, "_redis", side_effect=AssertionError("Duplicate Redis")
                ), patch.object(
                    duplicate,
                    "read_bytes",
                    side_effect=AssertionError("Duplicate original read"),
                ), patch.object(
                    native_catalog,
                    "_database",
                    side_effect=AssertionError("Canonical SQL"),
                ), patch.object(
                    native_catalog,
                    "_redis",
                    side_effect=AssertionError("Canonical Redis"),
                ), patch.object(
                    native_catalog,
                    "read_bytes",
                    side_effect=AssertionError("Canonical original read"),
                ):
                    original_read = duplicate.read_bytes
                    aliases.read = duplicate.read_bytes
                    with ReplayCatalog(directory).install():
                        outer_read = native_catalog.read_bytes
                        self.assertEqual(duplicate.read_bytes(path), raw)
                        self.assertEqual(aliases.read(path), raw)
                        self.assertEqual(aliases.load(path)["spells"]["42"]["id"], 42)
                        with self.assertRaises(MissingReproductionCatalog):
                            duplicate.load(native_catalog.DATA_ROOT / "unknown.json")
                        with ReplayCatalog(directory).install():
                            self.assertIs(
                                duplicate.read_bytes, native_catalog.read_bytes
                            )
                            self.assertEqual(
                                importlib.import_module(name).read_bytes(path), raw
                            )
                            self.assertEqual(duplicate.read_bytes(path), raw)
                        self.assertIs(native_catalog.read_bytes, outer_read)
                        self.assertIs(sys.modules[name], native_catalog)
                    self.assertIs(duplicate.read_bytes, original_read)
                    self.assertIs(aliases.read, original_read)
                self.assertIs(duplicate.load, original_load)
                self.assertIs(aliases.load, original_load)
                self.assertIs(sys.modules[name], duplicate)
                self.assertIs(parent.native_catalog, duplicate)
            finally:
                sys.modules.pop(aliases.__name__, None)
                sys.modules.pop(name, None)
                parent.__dict__.pop("native_catalog", None)
                if saved_module is not None:
                    sys.modules[name] = saved_module
                if saved_attribute is not None:
                    parent.native_catalog = saved_attribute

    def test_export_rejects_unpublished_consumed_document(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                native_catalog, "release", return_value="r"
            ), patch.object(
                native_catalog, "document_hashes", return_value={}
            ), patch.object(
                native_catalog, "_database", return_value=MagicMock()
            ):
                with CaptureCatalog(extra_documents=("missing.json",)) as capture:
                    with self.assertRaises(ValueError):
                        capture.export(directory)


if __name__ == "__main__":
    unittest.main()
