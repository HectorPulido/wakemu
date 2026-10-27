"""Installer verification retains sealed source pins across metadata releases."""
import gzip
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


class EnvironmentalProfileSourceCompatibilityTests(unittest.TestCase):
    def test_real_verifier_original_inventory_counts_and_changed_dependencies(self):
        from tools import install_environmental_profiles as installer
        from wakfu_server import native_catalog_compatibility as compatibility

        directory = Path(__file__).resolve().parents[1] / "data/installation"
        top = json.loads((directory / "manifest.json").read_bytes())
        descriptor = top["artifacts"]["native-catalogs"]
        raw = (directory / descriptor["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), descriptor["sha256"])
        manifest = json.loads(raw)
        current = manifest["active_revision"]
        release = next(
            row for row in manifest["releases"] if row["revision"] == current
        )
        hashes = {row["path"]: row["sha256"] for row in release["documents"]}
        proof_sha = hashes[compatibility.MANIFEST_DOCUMENT]
        proof = gzip.decompress(
            (directory / "catalogs/parts" / (proof_sha + ".json.gz")).read_bytes()
        )
        self.assertEqual(hashlib.sha256(proof).hexdigest(), proof_sha)
        original = next(
            row
            for row in json.loads(proof)["releases"]
            if row["document_count"] == 7490
        )
        pinned = original["revision"]
        self.assertNotEqual(pinned, current)
        original_hashes = {row["path"]: row["sha256"] for row in original["documents"]}
        self.assertEqual(len(installer.PROFILE_SOURCE_DOCUMENTS), 6)
        for path in installer.PROFILE_SOURCE_DOCUMENTS:
            self.assertEqual(original_hashes[path], hashes[path])

        profiles = dict(n=1270, sealed=1270, scenarios=1057, enabled=1270)
        pins = [pinned, current]
        active = current
        queries = []

        def query(sql, parameters=()):
            queries.append(sql)
            result = MagicMock()
            if sql.startswith("SELECT a.revision"):
                row = {"revision": active}
            elif sql.startswith("SELECT DISTINCT catalog_revision"):
                result.fetchall.return_value = [
                    dict(catalog_revision=pin) for pin in pins
                ]
                return result
            elif "FROM environmental_runtime_profiles" in sql:
                row = dict(profiles)
            elif "FROM environmental_regional_schedule_candidates" in sql:
                row = dict(n=1270)
            elif "WHERE enabled AND version<>9" in sql:
                row = dict(n=0)
            elif "FROM environmental_regional_schedule_policies" in sql:
                row = dict(n=90, sealed=90, enabled=90)
            elif "FROM archmonster_spawn_sources" in sql:
                row = dict(eligible=61, blocked=2)
            elif "FROM environmental_random_roster_active" in sql:
                row = dict(policy_version=installer.GENESIS, enabled=True)
            elif "FROM archmonster_spawn_active" in sql:
                row = dict(
                    policy_version="preserved-policy", enabled=True, cooldown_ms=1
                )
            else:
                raise AssertionError(sql)
            result.fetchone.return_value = row
            return result

        db = MagicMock()
        db.execute.side_effect = query
        historical_database = MagicMock()
        historical_db = (
            historical_database.connection.return_value.__enter__.return_value
        )
        historical_db.execute.return_value.fetchone.return_value = None

        def clear():
            compatibility._historical_documents.cache_clear()
            compatibility._current_documents.cache_clear()

        self.addCleanup(clear)
        with patch.object(
            compatibility.native_catalog, "release", return_value=current
        ), patch.object(
            compatibility.native_catalog, "_database", return_value=historical_database
        ), patch.object(
            compatibility.native_catalog, "document_hashes", return_value=hashes
        ), patch.object(
            compatibility.native_catalog, "read_published_bytes", return_value=proof
        ) as read:
            clear()
            receipt = installer.verify(db, current)
            self.assertEqual(receipt["source_catalog_revisions"], pins)
            self.assertEqual(
                (
                    receipt["profiles"],
                    receipt["sealed_profiles"],
                    receipt["native_scenarios"],
                ),
                (1270, 1270, 1057),
            )
            read.assert_called_once_with(compatibility.MANIFEST_DOCUMENT)
            self.assertTrue(all(sql.startswith("SELECT ") for sql in queries))
            for path in installer.PROFILE_SOURCE_DOCUMENTS:
                for kind in ("changed", "missing"):
                    clear()
                    altered = dict(hashes)
                    if kind == "changed":
                        altered[path] = "f" * 64
                    else:
                        del altered[path]
                    with self.subTest(path=path, kind=kind), patch.object(
                        compatibility.native_catalog,
                        "document_hashes",
                        return_value=altered,
                    ):
                        with self.assertRaisesRegex(ValueError, "dependency changed"):
                            installer.verify(db, current)
            clear()
            pins[:] = ["a" * 64]
            with self.assertRaisesRegex(ValueError, "unavailable"):
                installer.verify(db, current)
            pins[:] = [pinned]
            for field in ("n", "sealed", "scenarios"):
                profiles[field] -= 1
                with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, "1270 sealed profiles"
                ):
                    installer.verify(db, current)
                profiles[field] += 1
            active = pinned
            with self.assertRaisesRegex(ValueError, "differs from expected"):
                installer.verify(db, current)
