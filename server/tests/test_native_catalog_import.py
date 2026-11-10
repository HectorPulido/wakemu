"""Deterministic manifest and isolated PostgreSQL tests for catalog imports."""

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from postgres_case import PostgresCase
from tools.import_native_catalogs import (
    catalog_records,
    entity_key,
    import_catalogs,
    release_revision,
    source_manifest,
)


class NativeCatalogManifestTests(unittest.TestCase):
    def test_reference_field_is_used_as_the_entity_index_key(self):
        record = {"ref": 3017, "name": "Gobball"}

        self.assertEqual(entity_key(record, 8), "3017")
        self.assertEqual(
            list(catalog_records("monsters.json", {"monsters": [record]})),
            [("monsters", "3017", record)],
        )

    def test_duplicate_identities_and_literal_suffixes_keep_every_record(self):
        records = [
            {"ref": 8, "variant": "first"},
            {"ref": 8, "variant": "second"},
            {"ref": "8@0", "variant": "literal-zero"},
            {"ref": "8@1", "variant": "literal-one"},
        ]

        indexed = list(catalog_records("monsters.json", {"monsters": records}))
        keys = [key for _, key, _ in indexed]

        self.assertEqual(len(indexed), len(records))
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(
            dict(zip(keys, (record["variant"] for _, _, record in indexed))),
            {
                "8@0@0": "first",
                "8@1@1": "second",
                "8@0": "literal-zero",
                "8@1": "literal-one",
            },
        )

    def test_manifest_uses_sorted_posix_paths_and_content_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "z").mkdir()
            (root / "a.json").write_bytes(b'{"a":1}')
            (root / "z" / "b.json").write_bytes(b'{"b":2}')

            manifest = source_manifest(root)

            self.assertEqual(
                manifest,
                [
                    ("a.json", hashlib.sha256(b'{"a":1}').hexdigest(), 7),
                    ("z/b.json", hashlib.sha256(b'{"b":2}').hexdigest(), 7),
                ],
            )
            self.assertEqual(
                release_revision(manifest), release_revision(source_manifest(root))
            )

    def test_manifest_rejects_empty_source(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "No native JSON documents"):
                source_manifest(Path(directory))


@unittest.skipUnless(
    os.environ.get("WAKFU_POSTGRES_TEST_URL"), "Isolated PostgreSQL required"
)
class NativeCatalogImportPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        from wakfu_server.postgres import Database

        self.import_database = Database(
            self.database_url,
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
            min_size=1,
            max_size=2,
        )
        self.addCleanup(self.import_database.close)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def source(self, name="items.json", raw=None):
        raw = raw if raw is not None else b'{"items":{"42":{"id":42,"name":"test"}}}'
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def query(self, sql, params=()):
        with self.import_database.connection() as db:
            return db.execute(sql, params).fetchall()

    def test_import_stages_raw_document_and_keyed_records_then_activates(self):
        raw = b'{"items":{"42":{"id":42,"name":"test"}}}'
        self.source(raw=raw)

        result = import_catalogs(self.import_database, self.directory)

        self.assertTrue(result["activated"])
        self.assertEqual(result["documents"], 1)
        self.assertEqual(result["records"], 1)
        self.assertEqual(
            self.query("SELECT revision FROM native_catalog_active WHERE id=1")[0][
                "revision"
            ],
            result["revision"],
        )
        document = self.query(
            "SELECT raw,sha256,source_bytes,record_count FROM native_catalog_documents "
            "WHERE revision=%s AND path=%s",
            (result["revision"], "items.json"),
        )[0]
        self.assertEqual(bytes(document["raw"]), raw)
        self.assertEqual(document["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(document["source_bytes"], len(raw))
        self.assertEqual(document["record_count"], 1)
        self.assertEqual(
            self.query(
                "SELECT payload FROM native_catalog_records WHERE revision=%s AND path=%s "
                "AND collection=%s AND record_key=%s",
                (result["revision"], "items.json", "items", "42"),
            )[0]["payload"],
            {"id": 42, "name": "test"},
        )

    def test_stage_only_keeps_existing_activation_until_later_activation(self):
        self.source(raw=b'{"items":{"1":{"id":1}}}')
        first = import_catalogs(self.import_database, self.directory)
        self.source("next.json", b'{"items":{"2":{"id":2}}}')

        staged = import_catalogs(self.import_database, self.directory, activate=False)

        self.assertFalse(staged["activated"])
        self.assertEqual(
            self.query("SELECT revision FROM native_catalog_active WHERE id=1")[0][
                "revision"
            ],
            first["revision"],
        )
        activated = import_catalogs(self.import_database, self.directory, activate=True)
        self.assertEqual(activated["revision"], staged["revision"])
        self.assertEqual(
            self.query("SELECT revision FROM native_catalog_active WHERE id=1")[0][
                "revision"
            ],
            staged["revision"],
        )
        self.assertEqual(activated["imported"], 0)
        self.assertEqual(activated["skipped"], 2)

    def test_failed_record_write_rolls_back_document_and_retry_completes(self):
        from unittest.mock import patch

        from wakfu_server import native_shared_storage

        raw = b'{"items":{"9":{"id":9}}}'
        self.source(raw=raw)
        revision = release_revision(source_manifest(self.directory))

        copy_records = native_shared_storage.copy_records

        def partial_copy_then_fail(*args, **kwargs):
            copy_records(*args, **kwargs)
            raise RuntimeError("intentional catalog import failure")

        with patch.object(
            native_shared_storage, "copy_records", side_effect=partial_copy_then_fail
        ), self.assertRaisesRegex(Exception, "intentional catalog import failure"):
            import_catalogs(self.import_database, self.directory)
        self.assertEqual(
            self.query(
                "SELECT count(*) AS n FROM native_catalog_documents WHERE revision=%s",
                (revision,),
            )[0]["n"],
            0,
        )
        self.assertEqual(
            self.query(
                "SELECT complete FROM native_catalog_releases WHERE revision=%s",
                (revision,),
            )[0]["complete"],
            False,
        )

        result = import_catalogs(self.import_database, self.directory)
        self.assertEqual(result["revision"], revision)
        self.assertTrue(result["activated"])
        self.assertEqual(result["imported"], 1)

    def test_index_contract_survives_clone_and_is_cleared_by_copy_on_write(self):
        self.source("stable.json", b'{"items":{"7":{"value":1}}}')
        self.source("changed.json", b'{"items":{"1":{"value":1}}}')
        first = import_catalogs(self.import_database, self.directory)

        self.source("changed.json", b'{"items":{"1":{"value":2}}}')
        second = import_catalogs(self.import_database, self.directory)
        self.assertEqual(second["reused"], 1)
        contract_sql = (
            "SELECT contract_sha256 FROM native_catalog_document_index_contracts "
            "WHERE revision=%s AND path='stable.json'"
        )
        first_contract = self.query(contract_sql, (first["revision"],))[0][
            "contract_sha256"
        ]
        self.assertEqual(
            self.query(contract_sql, (second["revision"],))[0]["contract_sha256"],
            first_contract,
        )
        ids = self.query(
            "SELECT revision,index_set_id FROM native_catalog_document_links "
            "WHERE revision=ANY(%s) AND path='stable.json' ORDER BY revision",
            ([first["revision"], second["revision"]],),
        )
        self.assertEqual(ids[0]["index_set_id"], ids[1]["index_set_id"])

        staging_revision = "e" * 64
        with self.import_database.connection() as db:
            raw = b'{"items":{"7":{"value":1}}}'
            db.execute(
                "INSERT INTO native_catalog_releases "
                "(revision,document_count,source_bytes,complete) VALUES(%s,1,%s,false)",
                (staging_revision, len(raw)),
            )
            from wakfu_server.native_shared_storage import clone_documents

            clone_documents(
                db, staging_revision, first["revision"], only_paths=("stable.json",)
            )
            db.execute(
                "UPDATE native_catalog_records SET payload='\"mutated\"'::jsonb "
                "WHERE revision=%s AND path='stable.json' AND collection='items' AND record_key='7'",
                (staging_revision,),
            )
        self.assertEqual(self.query(contract_sql, (staging_revision,)), [])
        self.assertEqual(
            self.query(contract_sql, (first["revision"],))[0]["contract_sha256"],
            first_contract,
        )
        self.assertEqual(
            self.query(contract_sql, (second["revision"],))[0]["contract_sha256"],
            first_contract,
        )

        self.source("changed.json", b'{"items":{"1":{"value":3}}}')
        third = import_catalogs(self.import_database, self.directory)
        self.assertEqual(third["reused"], 1)
        self.assertEqual(
            self.query(
                "SELECT payload FROM native_catalog_records WHERE revision=%s "
                "AND path='stable.json' AND collection='items' AND record_key='7'",
                (third["revision"],),
            )[0]["payload"],
            {"value": 1},
        )


if __name__ == "__main__":
    unittest.main()
