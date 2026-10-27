"""Frozen treasure and generic reward sources survive unrelated publications."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


class TreasureSourceCompatibilityTests(unittest.TestCase):
    def test_frozen_attestors_fresh_inventory_warm_cache_and_changed_dependencies(self):
        from wakfu_server import native_catalog as catalog
        from wakfu_server import native_catalog_compatibility as compatibility
        from wakfu_server import (
            paid_containers,
            native_generic_rewards,
            treasure_chests,
            declared_treasure_rewards,
        )
        from wakfu_server.achievements import chest_open

        original_manifest = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "data/installation/catalogs/manifest.json"
            ).read_bytes()
        )
        original = next(
            row
            for row in original_manifest["releases"]
            if row["revision"] == original_manifest["active_revision"]
        )
        pinned = original["revision"]
        hashes = {row["path"]: row["sha256"] for row in original["documents"]}
        directory = Path(__file__).resolve().parents[1] / "data/installation/catalogs"
        active_manifest = json.loads(
            (directory / "manifest-rift-complete-metadata-v1.json").read_bytes()
        )
        current = active_manifest["active_revision"]
        active = next(
            row for row in active_manifest["releases"] if row["revision"] == current
        )
        published = {row["path"]: row["sha256"] for row in active["documents"]}
        proof_sha = published[compatibility.MANIFEST_DOCUMENT]
        proof = gzip.decompress(
            (directory / "parts" / (proof_sha + ".json.gz")).read_bytes()
        )
        self.assertEqual(hashlib.sha256(proof).hexdigest(), proof_sha)
        self.assertNotEqual(current, pinned)
        rule = dict(
            catalog_revision=pinned,
            map_id=527,
            object_id=25114,
            payload_hex="abcd",
            native_state_payload_hex="1234",
            geometry_sha256=hashes["combat-maps/527.json"],
            x=5,
            y=58,
            z=0,
        )
        generic_rule = dict(rule, object_id=123, state_payload_hex="1234")
        chest_rule = dict(
            rule,
            object_family="LootChest",
            attested_payload_hex=rule["payload_hex"],
            native_geometry_sha256=rule["geometry_sha256"],
            emote_id=None,
        )

        def declared_source():
            return declared_treasure_rewards._source(
                pinned,
                527,
                25114,
                "LootChest",
                "abcd",
                "1234",
                rule["geometry_sha256"],
                5,
                58,
                0,
            )

        records = {
            str(rule["object_id"]): dict(
                type="LootChest", map_id=527, x=5, y=58, z=0, payload_hex="abcd"
            ),
            str(generic_rule["object_id"]): dict(
                type="GenericActivableInteractiveElement",
                map_id=527,
                x=5,
                y=58,
                z=0,
                payload_hex="abcd",
            ),
        }
        database, db = MagicMock(), MagicMock()
        database.connection.return_value.__enter__.return_value = db
        queries = []

        def query(sql, parameters):
            queries.append((sql, parameters))
            cursor = MagicMock()
            if "FROM native_catalog_releases" in sql:
                self.assertEqual(parameters, (pinned,))
                cursor.fetchone.return_value = None  # Fresh: no old release rows.
            elif "FROM native_catalog_documents" in sql:
                self.assertEqual(parameters, (current, "combat-maps/527.json"))
                cursor.fetchone.return_value = {"sha256": published[parameters[1]]}
            else:
                self.fail("Unexpected source query: " + sql)
            return cursor

        def record(path, group, key):
            source = deepcopy(records[key])
            if Path(path).name == "native-interactive-states.json":
                source["payload_hex"] = "1234"
            return source

        def reset():
            compatibility._historical_documents.cache_clear()
            compatibility._current_documents.cache_clear()
            treasure_chests._native_authority.cache_clear()
            declared_treasure_rewards._source.cache_clear()

        reset()
        self.addCleanup(reset)
        db.execute.side_effect = query
        with patch.object(catalog, "release", return_value=current), patch.object(
            catalog, "_database", return_value=database
        ), patch.object(
            catalog, "document_hashes", return_value=published
        ), patch.object(
            catalog, "read_published_bytes", return_value=proof
        ) as read_proof, patch.object(
            catalog, "record", side_effect=record
        ) as read_record:
            paid_containers._source(rule)
            native_generic_rewards._source(generic_rule)
            chest_open._native_source(chest_rule)
            declared_source()
            self.assertEqual(rule["catalog_revision"], pinned)
            read_proof.assert_called_once_with(compatibility.MANIFEST_DOCUMENT)
            self.assertTrue(
                any("FROM native_catalog_documents" in sql for sql, _ in queries)
            )
            # A new actual publication must not reuse a warm frozen-revision
            # cache entry. The required document changed, while rule provenance
            # and every public call argument remain exactly the same.
            changed = dict(published, **{"native-map-objects.json": "b" * 64})
            next_revision = hashlib.sha256(
                b"".join(
                    path.encode() + b"\0" + checksum.encode() + b"\n"
                    for path, checksum in sorted(changed.items())
                )
            ).hexdigest()
            with patch.object(
                catalog, "release", return_value=next_revision
            ), patch.object(catalog, "document_hashes", return_value=changed):
                for operation in (
                    lambda: paid_containers._source(rule),
                    declared_source,
                ):
                    with self.assertRaisesRegex(ValueError, "dependency changed"):
                        operation()
            for operation in (
                lambda: paid_containers._source(rule),
                lambda: native_generic_rewards._source(generic_rule),
                lambda: chest_open._native_source(chest_rule),
                declared_source,
            ):
                for path in (
                    "native-map-objects.json",
                    "native-interactive-states.json",
                    "combat-maps/527.json",
                ):
                    reset()
                    read_record.reset_mock()
                    changed = dict(published, **{path: "b" * 64})
                    with patch.object(catalog, "document_hashes", return_value=changed):
                        with self.assertRaisesRegex(ValueError, "dependency changed"):
                            operation()
                    read_record.assert_not_called()
            reset()
            records[str(rule["object_id"])]["x"] += 1
            with self.assertRaisesRegex(ValueError, "declared native placement"):
                paid_containers._source(rule)
            records[str(generic_rule["object_id"])]["payload_hex"] = "ffff"
            with self.assertRaisesRegex(ValueError, "original world source"):
                native_generic_rewards._source(generic_rule)
