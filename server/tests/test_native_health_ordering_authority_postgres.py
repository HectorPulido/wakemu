"""Real isolated PostgreSQL lookup and immutable original DESC definitions."""
import json
import os
from pathlib import Path
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server import combat_health_ordering_authority as authority


class NativeHealthOrderingAuthorityPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        migration = Path(
            os.environ.get(
                "WAKFU_HEALTH_ORDERING_MIGRATION",
                Path(__file__).parents[1]
                / "migrations/270_native_descending_health_ordering_authority.sql",
            )
        )
        with self.store.connection() as db:
            installed = db.execute(
                "SELECT to_regclass('native_health_ordering_authority_versions')"
            ).fetchone()
            if next(iter(installed.values())) is None:
                if not migration.is_file():
                    self.skipTest(
                        "DESC authority migration draft or canonical source required"
                    )
                db.execute(migration.read_text(), prepare=False)
        self.proof = json.loads(
            (
                Path(__file__).with_name("fixtures")
                / "native_descending_health_ordering_authority.json"
            ).read_text()
        )
        self.enterContext(patch.object(authority, "_database", return_value=self.store))
        authority._for_revision.cache_clear()
        self.addCleanup(authority._for_revision.cache_clear)

    def test_nine_original_identities_and_catalog_release_isolation(self):
        result = authority._for_revision(self.proof["catalog_revision"])
        expected = self.proof["rows"]
        self.assertEqual(set(result), set(expected))
        for reference, row in result.items():
            self.assertEqual(
                dict(row, native_effect_flags=list(row["native_effect_flags"])),
                expected[reference],
            )
        self.assertEqual(authority._for_revision("f" * 64), {})
        self.assertEqual(result["325710"]["maximum_targets"], -1)
        self.assertEqual(result["351291"]["effect_class"], 330)

    def test_append_only_version_and_rows_reject_mutation(self):
        for sql in (
            "UPDATE native_health_ordering_authority_versions SET definition_count=10",
            "UPDATE native_health_ordering_authority_rows SET maximum_targets=1",
            "DELETE FROM native_health_ordering_authority_rows",
            "DELETE FROM native_health_ordering_authority_versions",
        ):
            with self.subTest(sql=sql), self.assertRaisesRegex(
                Exception, "append-only"
            ):
                with self.store.connection() as db:
                    db.execute(sql)
        self.assertEqual(
            len(authority._for_revision(self.proof["catalog_revision"])), 9
        )
