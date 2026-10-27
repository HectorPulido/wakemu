"""Real encounter guards retain immutable rows across additive publications."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class EncounterSourceCompatibilityTests(unittest.TestCase):
    def test_turn_order_and_nox_rows_use_verified_current_dependencies(self):
        from wakfu_server import native_catalog
        from wakfu_server import native_catalog_compatibility as compatibility
        from wakfu_server import combat_encounter_turn_end_order as ordering
        from wakfu_server.combat_nox_complex_loot_policy import (
            NoxComplexLootPolicy,
            validate_native_rows,
        )
        from tools.stage_rift_complete_metadata_catalog import read_document

        root = Path(__file__).resolve().parents[1]
        catalogs = root / "data/installation/catalogs"
        original_pack = json.loads((catalogs / "manifest.json").read_bytes())
        original = next(
            row
            for row in original_pack["releases"]
            if row["revision"] == original_pack["active_revision"]
        )
        current_pack = json.loads(
            (catalogs / "manifest-rift-complete-metadata-v1.json").read_bytes()
        )
        current = current_pack["active_revision"]
        active = next(
            row for row in current_pack["releases"] if row["revision"] == current
        )
        current_hashes = {row["path"]: row["sha256"] for row in active["documents"]}
        manifest_row = next(
            row
            for row in active["documents"]
            if row["path"] == compatibility.MANIFEST_DOCUMENT
        )
        source_manifest = read_document(catalogs, current_pack, manifest_row)
        self.assertNotEqual(current, original["revision"])
        self.assertEqual(source_manifest["releases"], [original])
        frozen = dict(
            policy="wakemu-rushu-cycle-regeneration-before-end-v1",
            authority="wakemu-reconstructed-observed-rushu-cycle-end-order",
            catalog_revision=original["revision"],
            map_id=1332,
            monster_references=[5306],
            boss_reference=5306,
            boss_constructor_state=7000,
            table_turns=[5, 10, 15, 20],
            event_ids=[1037, 1002],
        )
        self.assertIn(
            frozen["policy"],
            (root / "migrations/257_rushu_cycle_turn_end_order.sql").read_text(),
        )
        roles = SimpleNamespace(map_id=1332, monster_references=(5306,))
        rows = json.loads(
            (Path(__file__).parent / "fixtures/nox_complex_loot_rows.json").read_text()
        )
        digest = hashlib.sha256(
            json.dumps(
                sorted(rows, key=lambda row: row["reference_id"]),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        self.assertEqual(
            digest, "52480339c7c4810f2dcda7c3f08beeb23fc1734c77003c62e6064a956b3e8441"
        )
        nox = NoxComplexLootPolicy(
            "wakemu-nox-scored-complex-loot-v1",
            5664,
            "wakemu-nox-score-1.92-v1",
            3000000,
            original["revision"],
            digest,
            51,
            tuple(sorted(row["reference_id"] for row in rows)),
        )

        class Cursor:
            def __init__(self, value):
                self.value = value

            def fetchone(self):
                return deepcopy(self.value)

        class Database:
            @contextmanager
            def connection(self):
                yield self

            def execute(self, sql, parameters):
                if "FROM native_catalog_releases" in sql:
                    self.test.assertEqual(parameters, (original["revision"],))
                    return Cursor(None)  # Actual fresh installation condition.
                if "FROM encounter_turn_end_order_active" in sql:
                    self.test.assertEqual(parameters, (1332, [5306]))
                    return Cursor(dict(policy=frozen["policy"]))
                if "FROM encounter_turn_end_order_versions" in sql:
                    self.test.assertEqual(parameters, (frozen["policy"],))
                    return Cursor(frozen)
                raise AssertionError("Unexpected source DB query: " + sql)

        database = Database()
        database.test = self

        def read(name):
            self.assertEqual(name, compatibility.MANIFEST_DOCUMENT)
            return json.dumps(source_manifest).encode()

        def reset():
            ordering._version.cache_clear()
            compatibility._historical_documents.cache_clear()
            compatibility._current_documents.cache_clear()

        self.addCleanup(reset)
        reset()
        with patch.object(
            native_catalog, "release", return_value=current
        ), patch.object(
            native_catalog, "_database", return_value=database
        ), patch.object(
            native_catalog, "document_hashes", return_value=current_hashes
        ), patch.object(
            native_catalog, "read_published_bytes", side_effect=read
        ), patch.object(
            ordering, "_database", return_value=database
        ):
            fight = SimpleNamespace(phase="placement")
            self.assertEqual(
                ordering.freeze_turn_end_order_policy(fight, roles=roles), frozen
            )
            self.assertEqual(
                fight.native_turn_end_order_policy["catalog_revision"],
                original["revision"],
            )
            self.assertEqual(
                ordering.freeze_turn_end_order_policy(fight, roles=roles), frozen
            )
            validate_native_rows(nox, current, rows)
            validate_native_rows(nox, nox.catalog_revision, rows)
            mutated = deepcopy(rows)
            mutated[0]["probability"] += 1
            with self.assertRaisesRegex(ValueError, "probabilities or quantities"):
                validate_native_rows(nox, current, mutated)
            with self.assertRaisesRegex(ValueError, "current native source"):
                validate_native_rows(nox, "0" * 64, rows)
            for dependency in ordering.SOURCE_DEPENDENCIES:
                reset()
                changed = dict(current_hashes, **{dependency: "a" * 64})
                with patch.object(
                    native_catalog, "document_hashes", return_value=changed
                ):
                    candidate = SimpleNamespace(phase="placement")
                    with self.assertRaisesRegex(ValueError, "dependency changed"):
                        ordering.freeze_turn_end_order_policy(candidate, roles=roles)
                    self.assertFalse(hasattr(candidate, "native_turn_end_order_policy"))
            reset()
            with patch.object(
                native_catalog,
                "document_hashes",
                return_value=dict(
                    current_hashes, **{"monster-encyclopedia.json": "a" * 64}
                ),
            ):
                with self.assertRaisesRegex(ValueError, "dependency changed"):
                    validate_native_rows(nox, current, rows)
