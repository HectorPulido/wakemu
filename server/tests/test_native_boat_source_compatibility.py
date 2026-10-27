"""Boat source compatibility retains endpoint proofs and live-read freshness."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch


class NativeBoatSourceCompatibilityTests(unittest.TestCase):
    def test_real_boat_descriptor_unchanged_map_changed_map_and_live_revision(self):
        from wakfu_server import native_boat_arrivals as arrivals
        from wakfu_server import native_catalog_compatibility as compatibility

        server = Path(__file__).resolve().parents[1]
        sql = (
            server / "migrations/311_native_boat_arrival_only_authority.sql"
        ).read_text()
        authority = json.loads(
            re.search(r"VALUES\('native_boat_arrival_authority','(.*?)'::jsonb\)", sql)
            .group(1)
            .replace("''", "'")
        )
        contracts = json.loads(
            (server / "migrations/154_native_boat_contract_authority.sql")
            .read_text()
            .split("$native_boats$")[1]
        )
        pack = json.loads(
            (server / "data/installation/catalogs/manifest.json").read_bytes()
        )
        original = next(
            row
            for row in pack["releases"]
            if row["revision"] == authority["catalog_revision"]
        )
        pinned = original["revision"]
        hashes = {row["path"]: row["sha256"] for row in original["documents"]}
        path = "combat-maps/843.json"
        self.assertEqual(hashes[path], authority["arrivals"][0]["geometry_sha256"])
        current_hashes = dict(hashes, **{"unrelated-boat-test-metadata.json": "a" * 64})
        current = hashlib.sha256(
            b"".join(
                name.encode() + b"\0" + checksum.encode() + b"\n"
                for name, checksum in sorted(current_hashes.items())
            )
        ).hexdigest()

        class Cursor:
            def __init__(self, row=None, rows=()):
                self.row, self.rows = row, rows

            def fetchone(self):
                return self.row

            def fetchall(self):
                return self.rows

        class Settings:
            def execute(self, query, args):
                values = {
                    arrivals.SETTING: authority,
                    "native_boat_contracts": contracts,
                }
                return Cursor(dict(value=deepcopy(values[args[0]])))

        class Sources:
            fresh = False
            drift = False
            changed_during_read = False

            @contextmanager
            def connection(self):
                yield self

            def execute(self, query, args):
                if query.startswith("SELECT revision,"):
                    return Cursor(
                        None
                        if self.fresh
                        else {
                            key: original[key]
                            for key in (
                                "revision",
                                "document_count",
                                "source_bytes",
                                "complete",
                            )
                        }
                    )
                if query.startswith("SELECT path,"):
                    return Cursor(rows=original["documents"])
                if query.startswith("SELECT sha256"):
                    self.changed_during_read = self.drift
                    if args != (current, path):
                        raise AssertionError(
                            "Boat must read its actual current map document"
                        )
                    return Cursor(dict(sha256=current_hashes[path]))
                raise AssertionError("Unexpected source query: " + query)

        source = Sources()

        def reset():
            compatibility._historical_documents.cache_clear()
            compatibility._current_documents.cache_clear()
            source.changed_during_read = False

        def revision():
            return "f" * 64 if source.changed_during_read else current

        with patch.object(
            compatibility.native_catalog, "release", side_effect=revision
        ), patch.object(
            compatibility.native_catalog, "_database", return_value=source
        ), patch.object(
            compatibility.native_catalog, "document_hashes", return_value=current_hashes
        ), patch.object(
            compatibility.native_catalog,
            "read_published_bytes",
            return_value=json.dumps(
                {"policy": compatibility.MANIFEST_POLICY, "releases": [original]}
            ).encode(),
        ):
            try:
                for fresh in (False, True):
                    source.fresh = fresh
                    reset()
                    rows = arrivals.load(Settings())
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]["source"], (-1, 0, 49))
                    self.assertIn((0, 0, 48), rows[0]["targets"])
                    self.assertEqual(authority["catalog_revision"], pinned)

                reset()
                with patch.object(
                    compatibility.native_catalog,
                    "document_hashes",
                    return_value=dict(current_hashes, **{path: "b" * 64}),
                ):
                    with self.assertRaisesRegex(ValueError, "dependency changed"):
                        arrivals.load(Settings())

                # Metadata compatibility never relaxes a changing CURRENT
                # revision during one read, even if a map hash stayed equal.
                reset()
                source.drift = True
                with self.assertRaisesRegex(ValueError, "changed during validation"):
                    arrivals.load(Settings())
                source.drift = False

                reset()
                altered = deepcopy(contracts)
                altered["endpoints"] = [
                    dict(row, x=row["x"] + 1) if row["id"] == 35193 else row
                    for row in altered["endpoints"]
                ]
                with patch("wakfu_server.native_boats.load", return_value=altered):
                    with self.assertRaisesRegex(ValueError, "linked endpoint/column"):
                        arrivals.load(Settings())
            finally:
                reset()
