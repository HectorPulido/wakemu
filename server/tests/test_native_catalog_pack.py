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
        self.retired = []

    def execute(self, sql, params=()):
        if "native_catalog_active" in sql:
            return Result([{"revision": self.active}])
        if "native_catalog_retired_inventories" in sql:
            return Result(self.retired)
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
            self.assertNotIn("retired_inventories", pack)
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

    def test_new_pack_roundtrips_retired_source_inventory_without_payload(self):
        from tools.native_catalog_provenance import validated_retired_inventories

        db = CatalogSource()
        raw = b'{"retired": true}\n'
        document = {
            "path": "retired.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "source_bytes": len(raw),
            "record_count": 0,
        }
        identity = release_identity(
            [(document["path"], document["sha256"], document["source_bytes"])]
        )
        inventory = dict(
            revision=identity["revision"],
            document_count=1,
            source_bytes=len(raw),
            complete=True,
            identity_scheme=identity["identity_scheme"],
            manifest_sha256=identity["manifest_sha256"],
            documents=[document],
        )
        omitted_revision = next(
            revision for revision in db.releases if revision != db.active
        )
        omitted_sources, omitted_documents = db.releases[omitted_revision]
        omitted_inventory = dict(
            revision=omitted_revision,
            document_count=len(omitted_documents),
            source_bytes=sum(row["source_bytes"] for row in omitted_documents),
            complete=True,
            documents=[
                {key: row[key] for key in ("path", "sha256", "source_bytes")}
                for row in omitted_documents
            ],
        )
        normalized = validated_retired_inventories([inventory, omitted_inventory])
        db.retired = [
            {
                "revision": omitted_revision,
                "inventory": None,
                "document_count": omitted_inventory["document_count"],
                "source_bytes": omitted_inventory["source_bytes"],
                "complete": True,
            },
            {
                "revision": inventory["revision"],
                "inventory": inventory,
                "document_count": inventory["document_count"],
                "source_bytes": inventory["source_bytes"],
                "complete": True,
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # The active release has payload; an unselected complete live
            # release and a payload-free archived release ride as metadata.
            pack = writer.export(db, root / "pack", [])
            self.assertEqual(pack["retired_inventories"], normalized)
            self.assertNotIn(document["sha256"], pack["blobs"])
            active_hashes = {row["sha256"] for row in db.releases[db.active][1]}
            self.assertTrue(
                all(
                    row["sha256"] not in pack["blobs"]
                    for row in omitted_inventory["documents"]
                    if row["sha256"] not in active_hashes
                )
            )
            materialized = reader.unpack(root / "pack/manifest.json", root / "out")
            self.assertEqual(materialized["retired_inventories"], normalized)
            self.assertTrue((root / "out/catalog-manifest.json").is_file())
            self.assertFalse((root / "out/catalogs" / inventory["revision"]).exists())

            corrupted = json.loads((root / "pack/manifest.json").read_text())
            target = next(
                row
                for row in corrupted["retired_inventories"]
                if row["revision"] == inventory["revision"]
            )
            target["documents"][0]["sha256"] = "f" * 64
            (root / "pack/corrupt-manifest.json").write_text(json.dumps(corrupted))
            with self.assertRaisesRegex(ValueError, "does not match"):
                reader.unpack(root / "pack/corrupt-manifest.json", root / "bad")
            self.assertFalse((root / "bad").exists())

        self.assertEqual(
            normalized[0]["documents"][0].keys(), {"path", "sha256", "source_bytes"}
        )

    def test_clean_install_verifier_accepts_only_matching_inactive_archives(self):
        from tools.verify_clean_install import verify_native_release_storage

        raw = b"retired"
        document = {
            "path": "retired.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "source_bytes": len(raw),
        }
        identity = release_identity(
            [(document["path"], document["sha256"], document["source_bytes"])]
        )
        revision = identity["revision"]
        inventory = dict(
            revision=revision,
            document_count=1,
            source_bytes=len(raw),
            complete=True,
            identity_scheme=identity["identity_scheme"],
            manifest_sha256=identity["manifest_sha256"],
            documents=[document],
        )

        class Database:
            def __init__(self, *, totals=(0, 0), archive=inventory):
                self.totals = totals
                self.archive = archive

            def execute(self, sql, parameters):
                if "count(*),coalesce(sum" in sql:
                    return Result([self.totals])
                if "native_catalog_retired_inventories" in sql:
                    return Result([] if self.archive is None else [(self.archive,)])
                raise AssertionError("Unexpected verifier query")

        release = dict(revision=revision, document_count=1, source_bytes=len(raw))
        self.assertEqual(
            verify_native_release_storage(Database(), [release], "0" * 64),
            [revision],
        )
        with self.assertRaisesRegex(ValueError, "Active native catalog payload"):
            verify_native_release_storage(Database(), [release], revision)
        with self.assertRaisesRegex(ValueError, "still owns document payloads"):
            verify_native_release_storage(
                Database(totals=(1, len(raw))), [release], "0" * 64
            )
        corrupt = dict(inventory)
        corrupt["documents"] = [dict(document, sha256="f" * 64)]
        with self.assertRaisesRegex(ValueError, "does not match"):
            verify_native_release_storage(
                Database(archive=corrupt), [release], "0" * 64
            )


if __name__ == "__main__":
    unittest.main()
