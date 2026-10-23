"""Offline source-byte preservation, deduplication, and fail-closed materialization."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import export_native_catalog_pack as writer
from tools import unpack_native_catalog_pack as reader
from tools.import_native_catalogs import release_identity, source_manifest


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class CatalogSource:
    def __init__(self):
        common = b'{"native": [1,2,3], "source": "original"}\n'
        self.raw = [
            {"common.json": common},
            {"common.json": common, "maps/7.json": b'{"cells": []}\n'},
        ]
        self.releases = {}
        for sources in self.raw:
            documents = [
                {
                    "path": path,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "source_bytes": len(raw),
                    "record_count": 0,
                }
                for path, raw in sorted(sources.items())
            ]
            identity = release_identity(
                [(x["path"], x["sha256"], x["source_bytes"]) for x in documents]
            )
            self.releases[identity["revision"]] = (sources, documents)
        self.active = next(iter(self.releases))

    def execute(self, sql, params=()):
        if "native_catalog_active" in sql:
            return Result([{"revision": self.active}])
        if "native_catalog_releases" in sql:
            documents = self.releases[params[0]][1]
            return Result(
                [
                    {
                        "revision": params[0],
                        "complete": True,
                        "document_count": len(documents),
                        "source_bytes": sum(x["source_bytes"] for x in documents),
                    }
                ]
            )
        if "substring(raw" in sql:
            offset, size, revision, path = params
            return Result(
                [
                    {
                        "part": self.releases[revision][0][path][
                            offset - 1 : offset - 1 + size
                        ]
                    }
                ]
            )
        return Result(self.releases[params[0]][1])


class NativeCatalogPackTests(unittest.TestCase):
    def test_exact_two_release_roundtrip_dedup_and_tamper_rejection(self):
        db = CatalogSource()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(writer, "PART_BYTES", 16):
                pack = writer.export(db, root / "pack", list(db.releases))
                duplicate = writer.export(db, root / "same", list(db.releases))
            self.assertEqual(pack, duplicate)
            self.assertEqual(len(pack["blobs"]), 2)
            self.assertTrue(
                all(
                    x.stat().st_size < 100 * 1024 * 1024
                    for x in (root / "pack/parts").iterdir()
                )
            )
            manifest = root / "pack/manifest.json"
            materialized = reader.unpack(manifest, root / "out")
            for release in materialized["releases"]:
                revision = release["revision"]
                docs = root / "out/catalogs" / revision
                self.assertEqual(
                    source_manifest(docs),
                    [
                        (x["path"], x["sha256"], x["source_bytes"])
                        for x in release["documents"]
                    ],
                )
                for name, raw in db.releases[revision][0].items():
                    self.assertEqual((docs / name).read_bytes(), raw)
            part = next(iter(pack["blobs"].values()))["parts"][0]
            path = root / "pack" / part["path"]
            path.write_bytes(b"x" * path.stat().st_size)
            with self.assertRaisesRegex(ValueError, "compressed checksum"):
                reader.unpack(manifest, root / "corrupt")
            self.assertTrue((root / "corrupt/INCOMPLETE").exists())
            pack["releases"][0]["documents"][0]["path"] = "../escape.json"
            manifest.write_text(json.dumps(pack))
            with self.assertRaises(ValueError):
                reader.unpack(manifest, root / "escape")
            self.assertFalse((root / "escape").exists())


if __name__ == "__main__":
    unittest.main()
