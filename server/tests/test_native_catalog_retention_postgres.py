"""Native payload retirement preserves live readers and frozen source seals."""

import json
import os
from pathlib import Path
import tempfile
import uuid
from unittest.mock import patch

from postgres_case import PostgresCase


class NativeCatalogRetentionTests(PostgresCase):
    def test_replacement_rebinds_cross_schema_views_and_preserves_oids_and_privileges(
        self,
    ):
        from psycopg import sql
        from tools.compact_native_catalog import compact

        self._sources()
        first_schema = "reader_" + uuid.uuid4().hex
        second_schema = "reader_" + uuid.uuid4().hex
        schemas = (first_schema, second_schema)

        def cleanup_readers():
            with self.store.connection() as db:
                for schema in reversed(schemas):
                    db.execute(
                        sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
                    )

        self.addCleanup(cleanup_readers)
        with self.store.connection() as db:
            source_schema = db.execute("SELECT current_schema() AS name").fetchone()[
                "name"
            ]
            for schema in schemas:
                db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            db.execute(
                sql.SQL(
                    "CREATE VIEW {} AS SELECT * FROM native_catalog_documents"
                ).format(sql.Identifier(first_schema, "documents"))
            )
            db.execute(
                sql.SQL(
                    "CREATE VIEW {} AS SELECT * FROM native_catalog_records"
                ).format(sql.Identifier(second_schema, "records"))
            )
            db.execute(
                sql.SQL("CREATE VIEW {} AS SELECT path FROM {}").format(
                    sql.Identifier(second_schema, "nested"),
                    sql.Identifier(first_schema, "documents"),
                )
            )
            db.execute(
                sql.SQL("GRANT SELECT ON {} TO PUBLIC").format(
                    sql.Identifier(first_schema, "documents")
                )
            )
            db.execute("GRANT SELECT ON native_catalog_records TO PUBLIC")
            db.execute("GRANT SELECT(path) ON native_catalog_documents TO PUBLIC")
            # New staging objects inherit a different default grant, which must
            # not leak through when replacing the original reader tables.
            db.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT INSERT ON TABLES TO PUBLIC"
                ).format(sql.Identifier(source_schema))
            )
            before = db.execute(
                "SELECT c.oid,c.relowner,c.relacl::text FROM pg_class c "
                "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s) ORDER BY c.oid",
                (list(schemas),),
            ).fetchall()
        compact(self.store.database)
        with self.store.connection() as db:
            after = db.execute(
                "SELECT c.oid,c.relowner,c.relacl::text FROM pg_class c "
                "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s) ORDER BY c.oid",
                (list(schemas),),
            ).fetchall()
            self.assertEqual(before, after)
            for schema, name in (
                (first_schema, "documents"),
                (second_schema, "records"),
            ):
                self.assertEqual(
                    db.execute(
                        sql.SQL("SELECT count(DISTINCT revision) AS n FROM {}").format(
                            sql.Identifier(schema, name)
                        )
                    ).fetchone()["n"],
                    2,
                )
            self.assertEqual(
                db.execute(
                    sql.SQL("SELECT count(*) AS n FROM {}").format(
                        sql.Identifier(second_schema, "nested")
                    )
                ).fetchone()["n"],
                4,
            )
            grants = db.execute(
                "SELECT c.relname,x.privilege_type FROM pg_class c "
                "CROSS JOIN LATERAL aclexplode(c.relacl) x "
                "WHERE c.oid=ANY(ARRAY['native_catalog_documents'::regclass,'native_catalog_records'::regclass]) "
                "AND x.grantee=0 ORDER BY c.relname,x.privilege_type"
            ).fetchall()
            self.assertEqual(
                [tuple(row.values()) for row in grants],
                [("native_catalog_records", "SELECT")],
            )
            self.assertEqual(
                db.execute(
                    "SELECT x.privilege_type FROM pg_attribute a CROSS JOIN LATERAL aclexplode(a.attacl) x "
                    "WHERE a.attrelid='native_catalog_documents'::regclass AND a.attname='path' AND x.grantee=0"
                ).fetchone()["privilege_type"],
                "SELECT",
            )

    def _sources(self):
        from tools.import_native_catalogs import import_catalogs

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        source = Path(temporary.name)
        (source / "stable.json").write_text('{"items":[{"id":7,"value":1}]}')
        releases = []
        for version in range(4):
            (source / "changed.json").write_text(
                json.dumps({"items": [{"id": 1, "value": version}]})
            )
            releases.append(import_catalogs(self.store, source))
        return source, releases

    def test_retirement_keeps_two_and_session_pin_then_authenticates_archived_inventory(
        self,
    ):
        from tools.compact_native_catalog import compact
        from wakfu_server.postgres import Database
        from wakfu_server import (
            native_catalog,
            native_catalog_compatibility as compatibility,
        )

        source, releases = self._sources()
        first = releases[0]["revision"]
        last = releases[-1]["revision"]
        pin = Database(
            self.database_url,
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        self.addCleanup(pin.close)
        pin.pin_native_revision(first)
        result = compact(self.store.database)
        self.assertEqual(
            set(result["retained"]), {first, releases[-2]["revision"], last}
        )
        self.assertEqual(result["retired"], [releases[1]["revision"]])
        pin.close()
        again = compact(self.store.database)
        self.assertEqual(again["retired"], [first])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT revision) AS n FROM native_catalog_documents"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_catalog_releases"
                ).fetchone()["n"],
                4,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_catalog_retired_inventories"
                ).fetchone()["n"],
                2,
            )
        compatibility._historical_documents.cache_clear()
        compatibility._current_documents.cache_clear()
        self.addCleanup(compatibility._historical_documents.cache_clear)
        self.addCleanup(compatibility._current_documents.cache_clear)
        with patch.object(
            native_catalog, "_database", return_value=self.store
        ), patch.object(native_catalog, "release", return_value=last):
            compatibility.require_source_revision(first, ("stable.json",))
            with self.assertRaisesRegex(ValueError, "changed"):
                compatibility.require_source_revision(first, ("changed.json",))
        self.assertFalse(compact(self.store.database)["compacted"])
        # A retired original artifact can still be restored through the normal
        # importer; it is incomplete staging until every document has returned.
        from tools import import_native_catalogs as importer
        from tools.native_catalog_provenance import restore_retired_inventories

        with self.store.connection() as db:
            inventory = db.execute(
                "SELECT inventory FROM native_catalog_retired_inventories WHERE revision=%s",
                (first,),
            ).fetchone()["inventory"]
            db.execute(
                "DELETE FROM native_catalog_retired_inventories WHERE revision=%s",
                (first,),
            )
            db.execute(
                "DELETE FROM native_catalog_releases WHERE revision=%s", (first,)
            )
        self.assertEqual(restore_retired_inventories(self.store, [inventory]), 1)

        (source / "changed.json").write_text(
            json.dumps({"items": [{"id": 1, "value": 0}]})
        )
        original_records = importer.catalog_records

        def restored_records(path, document):
            with self.store.connection() as db:
                self.assertFalse(
                    db.execute(
                        "SELECT complete FROM native_catalog_releases WHERE revision=%s",
                        (first,),
                    ).fetchone()["complete"]
                )
            return original_records(path, document)

        with patch.object(importer, "catalog_records", side_effect=restored_records):
            restored = importer.import_catalogs(self.store, source, activate=False)
        self.assertEqual(restored["revision"], first)
        self.assertEqual(restored["records"], 2)

    def test_archived_complete_headers_do_not_consume_payload_retention_slots(self):
        from tools.compact_native_catalog import compact

        _, releases = self._sources()
        active = releases[-1]["revision"]
        compact(self.store.database, retain=2)
        middle = compact(self.store.database, keep=[active], retain=1)
        self.assertEqual(middle["retired"], [releases[-2]["revision"]])
        with self.store.connection() as db:
            archives = db.execute(
                "SELECT count(*) AS n FROM native_catalog_retired_inventories"
            ).fetchone()["n"]
            payloads = db.execute(
                "SELECT DISTINCT revision FROM native_catalog_documents"
            ).fetchall()
        self.assertEqual(archives, 3)
        self.assertEqual([row["revision"] for row in payloads], [active])

        replay = compact(self.store.database, retain=2)
        self.assertFalse(replay["compacted"])
        self.assertEqual(replay["retained"], [active])
        self.assertEqual(replay["retired"], [])

    def test_corrupt_retained_bytes_roll_back_archive_and_table_replacement(self):
        from tools.compact_native_catalog import compact

        _, releases = self._sources()
        with self.store.connection() as db:
            db.execute(
                "UPDATE native_catalog_documents SET raw=convert_to(replace(convert_from(raw,'UTF8'),'value','valuf'),'UTF8') "
                "WHERE revision=%s AND path='stable.json'",
                (releases[-1]["revision"],),
            )
        with self.assertRaisesRegex(ValueError, "checksum"):
            compact(self.store.database)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT revision) AS n FROM native_catalog_documents"
                ).fetchone()["n"],
                4,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_catalog_retired_inventories"
                ).fetchone()["n"],
                0,
            )

    def test_unchanged_document_index_reuses_contract_and_unchanged_release_skips_all(
        self,
    ):
        from tools import import_native_catalogs as importer

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        source = Path(temporary.name)
        (source / "stable.json").write_text('{"items":[{"id":7,"value":1}]}')
        changed = source / "changed.json"
        changed.write_text('{"items":[{"id":1,"value":1}]}')
        importer.import_catalogs(self.store, source)
        changed.write_text('{"items":[{"id":1,"value":2}]}')
        original = importer.catalog_records

        def records(path, document):
            self.assertNotEqual(
                path, "stable.json", "Unchanged document must not regenerate records"
            )
            return original(path, document)

        with patch.object(importer, "catalog_records", side_effect=records):
            result = importer.import_catalogs(self.store, source)
        self.assertEqual(result["reused"], 1)
        self.assertEqual(result["imported"], 1)
        with patch.object(
            importer,
            "catalog_records",
            side_effect=AssertionError("Unchanged release regenerated"),
        ):
            replay = importer.import_catalogs(self.store, source)
        self.assertEqual(replay["skipped"], 2)
        self.assertEqual(replay["imported"], 0)
