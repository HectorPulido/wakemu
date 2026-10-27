"""Source compatibility uses real published inventories, never revision aliases."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


class NativeCatalogCompatibilityTests(unittest.TestCase):
    def test_original_inventory_documents_allow_only_unchanged_dependencies(self):
        from wakfu_server import native_catalog_compatibility as compatibility

        manifest = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "data/installation/catalogs/manifest.json"
            ).read_bytes()
        )
        original = deepcopy(
            next(
                row
                for row in manifest["releases"]
                if row["revision"] == manifest["active_revision"]
            )
        )
        pinned = original["revision"]
        original_hashes = {row["path"]: row["sha256"] for row in original["documents"]}
        dependencies = ("monsters.json", "monster-encyclopedia.json")
        self.assertTrue(all(path in original_hashes for path in dependencies))
        current_hashes = dict(
            original_hashes, **{"new-unrelated-metadata.json": "a" * 64}
        )
        current = hashlib.sha256(
            b"".join(
                path.encode() + b"\0" + checksum.encode() + b"\n"
                for path, checksum in sorted(current_hashes.items())
            )
        ).hexdigest()
        database, db = MagicMock(), MagicMock()
        database.connection.return_value.__enter__.return_value = db

        def reset():
            compatibility._historical_documents.cache_clear()
            compatibility._current_documents.cache_clear()
            db.execute.reset_mock()
            db.execute.side_effect = None

        with patch.object(
            compatibility.native_catalog, "release", return_value=current
        ), patch.object(
            compatibility.native_catalog, "_database", return_value=database
        ), patch.object(
            compatibility.native_catalog, "document_hashes", return_value=current_hashes
        ), patch.object(
            compatibility.native_catalog, "read_published_bytes"
        ) as read:
            # A real retained complete release proves the old source, while an
            # unrelated appended document does not invalidate sealed profiles.
            reset()
            db.execute.return_value.fetchone.return_value = {
                key: original[key]
                for key in ("revision", "document_count", "source_bytes", "complete")
            }
            db.execute.return_value.fetchall.return_value = original["documents"]
            compatibility.require_source_revision(pinned, dependencies)
            read.assert_not_called()
            self.assertEqual(original["revision"], pinned)

            # Fresh installations may not retain the old database release.
            reset()
            db.execute.return_value.fetchone.return_value = None
            source_document = {
                "policy": compatibility.MANIFEST_POLICY,
                "releases": [original],
            }
            read.return_value = json.dumps(source_document).encode()
            compatibility.require_source_revision(pinned, dependencies)
            read.assert_called_once_with(compatibility.MANIFEST_DOCUMENT)

            for kind in ("changed", "missing"):
                reset()
                altered = dict(current_hashes)
                if kind == "changed":
                    altered[dependencies[0]] = "b" * 64
                else:
                    del altered[dependencies[0]]
                with patch.object(
                    compatibility.native_catalog,
                    "document_hashes",
                    return_value=altered,
                ):
                    with self.assertRaisesRegex(ValueError, "dependency changed"):
                        compatibility.require_source_revision(pinned, dependencies)

            for kind in (
                "checksum",
                "count",
                "size",
                "incomplete",
                "duplicate",
                "unknown",
            ):
                reset()
                broken = deepcopy(source_document)
                row = broken["releases"][0]
                if kind == "checksum":
                    row["documents"][0]["sha256"] = "c" * 64
                elif kind == "count":
                    row["document_count"] -= 1
                elif kind == "size":
                    row["source_bytes"] -= 1
                elif kind == "incomplete":
                    row["complete"] = False
                elif kind == "duplicate":
                    broken["releases"].append(deepcopy(row))
                else:
                    broken["releases"] = []
                read.return_value = json.dumps(broken).encode()
                with self.assertRaises(ValueError, msg=kind):
                    compatibility.require_source_revision(pinned, dependencies)

            # No blanket allowance for unknown/malformed dependencies, and no
            # historical/database reads for the original exact-current case.
            for required in (
                (),
                ("../monsters.json",),
                ("monsters.json", "monsters.json"),
            ):
                with self.assertRaises(ValueError):
                    compatibility.require_source_revision(pinned, required)
            reset()
            read.reset_mock()
            compatibility.require_source_revision(current, dependencies)
            db.execute.assert_not_called()
            read.assert_not_called()
        reset()

    def test_real_destroy_and_recurring_attestors_use_current_equivalent_sources(self):
        from wakfu_server import native_catalog_compatibility as compatibility
        from wakfu_server.objectives import environmental_monster_actions as destroy
        from wakfu_server.objectives import environmental_recurring_storage as recurring
        from wakfu_server.objectives import (
            environmental_archmonster_runtime as archmonster,
        )
        from wakfu_server.dungeon_runtime_config import canonical_hash

        manifest = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "data/installation/catalogs/manifest.json"
            ).read_bytes()
        )
        original = next(
            row
            for row in manifest["releases"]
            if row["revision"] == manifest["active_revision"]
        )
        pinned = original["revision"]
        hashes = {row["path"]: row["sha256"] for row in original["documents"]}
        current_hashes = dict(hashes, **{"unrelated-source-metadata.json": "a" * 64})
        current = hashlib.sha256(
            b"".join(
                path.encode() + b"\0" + checksum.encode() + b"\n"
                for path, checksum in sorted(current_hashes.items())
            )
        ).hexdigest()
        plan = {
            "definition_id": 91,
            "rooms": [
                {"order": 1, "monsters": [{"role": "boss", "ref_id": 41, "count": 1}]}
            ],
        }
        action = dict(
            native_class="aMg",
            d=3,
            aGJ=3,
            clT="",
            getDuration=0,
            cbH=0,
            clx=7,
            csI=False,
            csJ=True,
            csK=False,
        )
        record = {"ref": 41, "world_actions": [action]}
        database, db, cursor = MagicMock(), MagicMock(), MagicMock()
        database.connection.return_value.__enter__.return_value = db

        def query(sql, parameters):
            if "FROM native_catalog_releases" in sql:
                cursor.fetchone.return_value = None
            elif (
                sql
                == "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s"
            ):
                self.assertEqual(parameters, (current, "monsters.json"))
                cursor.fetchone.return_value = {"sha256": hashes["monsters.json"]}
            elif "FROM dungeon_runtime_configurations" in sql:
                cursor.fetchone.return_value = {
                    "configuration": {"compiled_plan": plan}
                }
            else:
                self.fail("Unexpected old-source SQL dependency: " + sql)
            return cursor

        db.execute.side_effect = query
        proof = json.dumps(
            {"policy": compatibility.MANIFEST_POLICY, "releases": [original]}
        ).encode()
        compatibility._historical_documents.cache_clear()
        compatibility._current_documents.cache_clear()
        self.addCleanup(compatibility._historical_documents.cache_clear)
        self.addCleanup(compatibility._current_documents.cache_clear)
        self.addCleanup(destroy._native_destroy_action.cache_clear)
        self.addCleanup(recurring._daily_source.cache_clear)
        with patch.object(
            compatibility.native_catalog, "release", return_value=current
        ), patch.object(
            compatibility.native_catalog, "_database", return_value=database
        ), patch.object(
            compatibility.native_catalog, "document_hashes", return_value=current_hashes
        ), patch.object(
            compatibility.native_catalog, "read_published_bytes", return_value=proof
        ), patch.object(
            compatibility.native_catalog, "record", return_value=record
        ) as read_record:
            destroy._native_destroy_action.cache_clear()
            recurring._daily_source.cache_clear()
            self.assertEqual(
                destroy._native_destroy_action(pinned, 41, 3)["native"], action
            )
            self.assertTrue(
                recurring._daily_source(
                    pinned,
                    "monsters.json",
                    hashes["monsters.json"],
                    41,
                    "bounded-qualification",
                    1,
                    canonical_hash(plan),
                    91,
                    1,
                )
            )
            self.assertEqual(read_record.call_count, 2)
            self.assertEqual(
                archmonster._current_monsters_sha(current), hashes["monsters.json"]
            )
            with patch.object(
                compatibility.native_catalog, "release", side_effect=(current, "c" * 64)
            ):
                with self.assertRaisesRegex(ValueError, "catalog changed"):
                    archmonster._current_monsters_sha(current)
            # A required source change is rejected before either actual record
            # reader or dungeon authority can observe/apply the new source.
            for path, operation in (
                (
                    "monster-encyclopedia.json",
                    lambda: destroy._native_destroy_action(pinned, 41, 3),
                ),
                (
                    "monsters.json",
                    lambda: recurring._daily_source(
                        pinned,
                        "monsters.json",
                        hashes["monsters.json"],
                        41,
                        "bounded-qualification",
                        1,
                        canonical_hash(plan),
                        91,
                        1,
                    ),
                ),
            ):
                compatibility._current_documents.cache_clear()
                destroy._native_destroy_action.cache_clear()
                recurring._daily_source.cache_clear()
                read_record.reset_mock()
                changed = dict(current_hashes, **{path: "b" * 64})
                with patch.object(
                    compatibility.native_catalog,
                    "document_hashes",
                    return_value=changed,
                ):
                    with self.assertRaisesRegex(ValueError, "dependency changed"):
                        operation()
                read_record.assert_not_called()
