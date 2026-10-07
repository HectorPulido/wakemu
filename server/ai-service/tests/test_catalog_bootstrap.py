"""Direct image-time catalogue provisioning without HTTP or filtering."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wakfu_ai.context.catalog_bootstrap import provision
from wakfu_ai.context.context_store import ContextStore
from wakfu_ai.bridge.world_bridge import _json_bytes


class CountingStore(ContextStore):
    def __init__(self, root):
        super().__init__(root)
        self.imports = []

    def import_file(self, source, digest, size):
        self.imports.append((digest, size))
        return super().import_file(source, digest, size)


class CatalogBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.store = CountingStore(self.base / "store")

    def tearDown(self):
        self.temporary.cleanup()

    def test_provisions_every_extension_and_binary_exactly_and_seals_catalog(self):
        source = self.base / "world"
        (source / "protocol" / "future").mkdir(parents=True)
        (source / "engine").mkdir()
        contents = {
            "protocol/known.json": b'{"id":1}',
            "protocol/future/opaque.catalog-v8": b"\x00\xff\x80\x10new format\n",
            "protocol/.hidden.capture": bytes(range(256)),
            "engine/module.native": b"engine\x00binary\xfe",
            "engine/empty.asset": b"",
        }
        for relative, payload in contents.items():
            (source / relative).write_bytes(payload)

        result = provision(
            {"protocol": source / "protocol", "engine": source / "engine"}, self.store
        )

        self.assertEqual(result["entries"], len(contents))
        manifest = self.store.json(result["sha256"])
        self.assertEqual(manifest["format"], "wakfu-complete-context-1")
        self.assertEqual(
            {entry["path"] for entry in manifest["entries"]},
            {
                "protocol/known.json",
                "protocol/future/opaque.catalog-v8",
                "protocol/.hidden.capture",
                "engine/module.native",
                "engine/empty.asset",
            },
        )
        self.assertTrue(self.store.manifest(result["sha256"])["complete"])
        for entry in manifest["entries"]:
            relative = entry["path"].split("/", 1)[1]
            source_path = (source / entry["path"].split("/", 1)[0]) / relative
            payload = source_path.read_bytes()
            self.assertEqual(entry["size"], len(payload))
            self.assertEqual(entry["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(self.store.read(entry["sha256"]), payload)
        manifest_bytes = _json_bytes(manifest)
        self.assertEqual(result["sha256"], hashlib.sha256(manifest_bytes).hexdigest())
        self.assertEqual(self.store.read(result["sha256"]), manifest_bytes)
        self.assertEqual(result["bytes"], sum(map(len, contents.values())))

    def test_reuses_identical_hashes_locally_without_http(self):
        source = self.base / "same-hash"
        (source / "nested").mkdir(parents=True)
        payload = b"same immutable asset\x00\xfe"
        (source / "first.future").write_bytes(payload)
        (source / "nested" / "second.unknown").write_bytes(payload)
        expected = hashlib.sha256(payload).hexdigest()

        with patch(
            "urllib.request.urlopen",
            side_effect=AssertionError("bootstrap must stay local"),
        ):
            result = provision({"assets": source}, self.store)

        manifest = self.store.json(result["sha256"])
        self.assertEqual(
            [entry["path"] for entry in manifest["entries"]],
            ["assets/first.future", "assets/nested/second.unknown"],
        )
        self.assertEqual({entry["sha256"] for entry in manifest["entries"]}, {expected})
        self.assertEqual(self.store.read(expected), payload)
        # One content-addressed blob backs both catalogue paths.
        self.assertEqual(
            sum(path.name == expected for path in (self.base / "store").iterdir()), 1
        )
        self.assertEqual(
            self.store.manifest(result["sha256"]),
            {"complete": True, "missing": [], "entries": 2},
        )

    def test_complete_world_root_and_sdk_use_the_world_bridge_manifest_paths(self):
        source = self.base / "complete-world"
        for directory in ("protocol", "wakfu_server", "ai-service", "migrations"):
            (source / directory).mkdir(parents=True)
        files = {
            "protocol/map.native": b"map",
            "wakfu_server/effect.py": b"effect",
            "ai-service/future_adapter.py": b"adapter",
            "migrations/future.sql": b"migration",
            "local_game_server.py": b"entry",
        }
        for relative, payload in files.items():
            (source / relative).write_bytes(payload)
        from wakfu_ai.bridge.world_bridge import CompleteContextExporter

        roots = {
            "catalog": source / "protocol",
            "engine": source / "wakfu_server",
            "server": source,
        }
        result = provision(roots, self.store)
        manifest, _ = CompleteContextExporter(roots).inventory()
        self.assertEqual(self.store.json(result["sha256"]), manifest)
        self.assertEqual(result["entries"], 7)
        self.assertIn(
            "server/ai-service/future_adapter.py",
            {e["path"] for e in manifest["entries"]},
        )
        self.assertIn(
            "server/migrations/future.sql", {e["path"] for e in manifest["entries"]}
        )
        self.assertTrue(
            all(self.store.has(e["sha256"], e["size"]) for e in manifest["entries"])
        )

    def test_empty_roots_provision_a_valid_empty_catalog(self):
        source = self.base / "empty"
        source.mkdir()

        result = provision({"empty-catalogue": source}, self.store)

        self.assertEqual(result["entries"], 0)
        self.assertEqual(result["bytes"], 0)
        self.assertEqual(
            self.store.json(result["sha256"]),
            {"format": "wakfu-complete-context-1", "entries": []},
        )
        self.assertEqual(
            self.store.manifest(result["sha256"]),
            {"complete": True, "missing": [], "entries": 0},
        )

    def test_changed_or_corrupt_source_is_rejected_before_catalog_seals(self):
        source = self.base / "mutating"
        source.mkdir()
        asset = source / "moving.bin"
        asset.write_bytes(b"first version")

        class MutatingStore(ContextStore):
            def import_file(inner, path, digest, size):
                Path(path).write_bytes(b"second version")
                return super(MutatingStore, inner).import_file(path, digest, size)

        with self.assertRaisesRegex(ValueError, "Provisioned catalogue asset changed"):
            provision({"world": source}, MutatingStore(self.base / "corrupt-store"))
        self.assertEqual(list((self.base / "corrupt-store").glob("*.partial")), [])
        self.assertFalse(
            any(
                len(path.name) == 64 for path in (self.base / "corrupt-store").iterdir()
            )
        )


if __name__ == "__main__":
    unittest.main()
