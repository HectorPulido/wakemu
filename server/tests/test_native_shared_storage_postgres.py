"""Legacy conversion, exact sharing, and copy-on-write native catalog checks."""

import hashlib
import os
from pathlib import Path
import tempfile
import uuid

from postgres_case import PostgresCase


class NativeSharedStoragePostgresTests(PostgresCase):
    def test_360_upgrade_preserves_custom_empty_reader_until_explicit_compaction(self):
        from psycopg import sql
        from psycopg.conninfo import make_conninfo
        from wakfu_server.postgres import Database, migrate
        from tools.compact_native_storage import compact

        source_dir = Path(__file__).resolve().parents[1] / "migrations"
        with tempfile.TemporaryDirectory() as prefix_dir_name:
            prefix_dir = Path(prefix_dir_name)
            for migration in source_dir.glob("*.sql"):
                if int(migration.name[:3]) <= 360:
                    (prefix_dir / migration.name).symlink_to(migration)
            prefix_dir.joinpath("360_native_catalog_shared_storage.sql").unlink()

            admin = Database(
                self.database_url,
                password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
            )
            self.addCleanup(admin.close)
            schema = "upgrade_" + uuid.uuid4().hex
            reader_schema = "reader_" + uuid.uuid4().hex
            with admin.connection() as db:
                db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
                db.execute(
                    sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(reader_schema))
                )

            def cleanup_schemas():
                with admin.connection() as db:
                    db.execute(
                        sql.SQL("DROP SCHEMA {} CASCADE").format(
                            sql.Identifier(reader_schema)
                        )
                    )
                    db.execute(
                        sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
                    )

            self.addCleanup(cleanup_schemas)
            database_url = make_conninfo(
                self.database_url, options=f"-c search_path={schema}"
            )
            upgrade_db = Database(
                database_url,
                password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
            )
            self.addCleanup(upgrade_db.close)
            with upgrade_db.connection() as db:
                migrate(db, prefix_dir)
            with upgrade_db.connection() as db:
                db.execute(
                    sql.SQL(
                        "CREATE VIEW {} AS SELECT * FROM native_catalog_documents"
                    ).format(sql.Identifier(reader_schema, "native_documents"))
                )
                db.execute("GRANT SELECT ON native_catalog_documents TO PUBLIC")
                db.execute(
                    sql.SQL("GRANT SELECT ON {} TO PUBLIC").format(
                        sql.Identifier(reader_schema, "native_documents")
                    )
                )
                before = db.execute(
                    "SELECT 'native_catalog_documents'::regclass::oid AS base_oid,"
                    f"'{reader_schema}.native_documents'::regclass::oid AS reader_oid"
                ).fetchone()
                self.assertEqual(
                    db.execute(
                        "SELECT relkind FROM pg_class "
                        "WHERE oid='native_catalog_documents'::regclass"
                    ).fetchone()["relkind"],
                    "r",
                )

            with upgrade_db.connection() as db:
                migrate(db, source_dir)
            with upgrade_db.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT relkind FROM pg_class "
                        "WHERE oid='native_catalog_documents'::regclass"
                    ).fetchone()["relkind"],
                    "r",
                )
                after_migration = db.execute(
                    "SELECT 'native_catalog_documents'::regclass::oid AS base_oid,"
                    f"'{reader_schema}.native_documents'::regclass::oid AS reader_oid"
                ).fetchone()
                self.assertEqual(after_migration["base_oid"], before["base_oid"])
                self.assertEqual(after_migration["reader_oid"], before["reader_oid"])
                self.assertEqual(
                    db.execute(
                        "SELECT EXISTS(SELECT 1 FROM aclexplode(relacl) "
                        "WHERE grantee=0 AND privilege_type='SELECT') AS granted "
                        "FROM pg_class WHERE oid='native_catalog_documents'::regclass"
                    ).fetchone()["granted"],
                    True,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT EXISTS(SELECT 1 FROM aclexplode(relacl) "
                        "WHERE grantee=0 AND privilege_type='SELECT') AS granted "
                        f"FROM pg_class WHERE oid='{reader_schema}.native_documents'::regclass"
                    ).fetchone()["granted"],
                    True,
                )

            result = compact(upgrade_db)
            self.assertTrue(result["compacted"])
            with upgrade_db.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT relkind FROM pg_class "
                        "WHERE oid='native_catalog_documents'::regclass"
                    ).fetchone()["relkind"],
                    "v",
                )
                after_compaction = db.execute(
                    f"SELECT '{reader_schema}.native_documents'::regclass::oid AS reader_oid"
                ).fetchone()
                self.assertEqual(after_compaction["reader_oid"], before["reader_oid"])
                self.assertTrue(
                    db.execute(
                        sql.SQL("SELECT count(*) AS n FROM {} ").format(
                            sql.Identifier(reader_schema, "native_documents")
                        )
                    ).fetchone()["n"]
                    == 0
                )
                self.assertEqual(
                    db.execute(
                        "SELECT EXISTS(SELECT 1 FROM aclexplode(relacl) "
                        "WHERE grantee=0 AND privilege_type='SELECT') AS granted "
                        "FROM pg_class WHERE oid='native_catalog_documents'::regclass"
                    ).fetchone()["granted"],
                    True,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT EXISTS(SELECT 1 FROM aclexplode(relacl) "
                        "WHERE grantee=0 AND privilege_type='SELECT') AS granted "
                        f"FROM pg_class WHERE oid='{reader_schema}.native_documents'::regclass"
                    ).fetchone()["granted"],
                    True,
                )

    def _legacy_layout(self, *, corrupt=False, valid_revisions=False):
        """Replace empty-install views with the pre-360 physical schema."""
        raw_shared = b'{"source": "identical"}\n'
        raw_other = b'{"source": "different"}\n'
        raw_shared_sha = hashlib.sha256(raw_shared).hexdigest()
        raw_other_sha = hashlib.sha256(raw_other).hexdigest()
        revision_a, revision_b = "a" * 64, "b" * 64
        if valid_revisions:
            from tools.import_native_catalogs import release_revision

            revision_a = release_revision(
                [
                    ("a.json", raw_shared_sha, len(raw_shared)),
                    ("b.json", raw_other_sha, len(raw_other)),
                ]
            )
            revision_b = release_revision([("a.json", raw_shared_sha, len(raw_shared))])
        with self.store.connection() as db:
            db.execute("DROP VIEW native_catalog_records")
            db.execute("DROP VIEW native_catalog_documents")
            contracts = db.execute(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid='native_catalog_document_index_contracts'::regclass "
                "AND contype='f'"
            ).fetchall()
            for row in contracts:
                db.execute(
                    f"ALTER TABLE native_catalog_document_index_contracts DROP CONSTRAINT {row['conname']}"
                )
            db.execute(
                "CREATE TABLE native_catalog_documents ("
                "revision text NOT NULL REFERENCES native_catalog_releases(revision),"
                "path text NOT NULL,raw bytea NOT NULL,sha256 text NOT NULL,"
                "source_bytes bigint NOT NULL,record_count integer NOT NULL CHECK(record_count>=0),"
                "PRIMARY KEY(revision,path),CHECK(source_bytes=octet_length(raw)))"
            )
            db.execute(
                "CREATE TABLE native_catalog_records ("
                "revision text NOT NULL,path text NOT NULL,collection text NOT NULL,"
                "record_key text NOT NULL,payload jsonb NOT NULL,"
                "PRIMARY KEY(revision,path,collection,record_key),"
                "FOREIGN KEY(revision,path) REFERENCES native_catalog_documents(revision,path))"
            )
            db.execute(
                "ALTER TABLE native_catalog_document_index_contracts "
                "ADD FOREIGN KEY(revision,path) REFERENCES native_catalog_documents(revision,path)"
            )
            db.execute(
                "CREATE VIEW native_catalog_legacy_rows AS "
                "SELECT revision,path,raw FROM native_catalog_documents"
            )
            db.execute(
                "CREATE VIEW native_catalog_legacy_nested AS "
                "SELECT revision,path,raw FROM native_catalog_legacy_rows"
            )
            db.execute("GRANT SELECT ON native_catalog_legacy_rows TO PUBLIC")
            db.execute(
                "INSERT INTO native_catalog_releases "
                "(revision,document_count,source_bytes,complete) "
                "VALUES(%s,2,%s,false),(%s,1,%s,false)",
                (
                    revision_a,
                    len(raw_shared) + len(raw_other),
                    revision_b,
                    len(raw_shared),
                ),
            )
            bad_raw = b'{"source": "corrupted"}\n' if corrupt else raw_shared
            db.execute(
                "INSERT INTO native_catalog_documents "
                "(revision,path,raw,sha256,source_bytes,record_count) "
                "VALUES(%s,'a.json',%s,%s,%s,1),(%s,'b.json',%s,%s,%s,1),"
                "(%s,'a.json',%s,%s,%s,1)",
                (
                    revision_a,
                    bad_raw,
                    raw_shared_sha,
                    len(raw_shared),
                    revision_a,
                    raw_other,
                    raw_other_sha,
                    len(raw_other),
                    revision_b,
                    raw_shared,
                    raw_shared_sha,
                    len(raw_shared),
                ),
            )
            db.execute(
                "INSERT INTO native_catalog_records "
                "(revision,path,collection,record_key,payload) VALUES"
                "(%s,'a.json','items','1','1'::jsonb),"
                "(%s,'b.json','items','1','1'::jsonb),"
                "(%s,'a.json','items','1','1.0'::jsonb)",
                (revision_a, revision_a, revision_b),
            )
            db.execute(
                "UPDATE native_catalog_releases SET complete=true "
                "WHERE revision=ANY(%s)",
                ([revision_a, revision_b],),
            )
            db.execute(
                "INSERT INTO native_catalog_active(id,revision) VALUES(1,%s)",
                (revision_b,),
            )
            identities = db.execute(
                "SELECT 'native_catalog_legacy_rows'::regclass::oid AS rows_oid,"
                "'native_catalog_legacy_nested'::regclass::oid AS nested_oid"
            ).fetchone()
        return revision_a, revision_b, raw_shared, raw_other, dict(identities)

    def test_legacy_conversion_preserves_bytes_numeric_json_and_view_copy_on_write(
        self,
    ):
        from tools.compact_native_storage import compact

        revision_a, revision_b, raw_shared, raw_other, old_views = self._legacy_layout()
        result = compact(self.store.database)
        self.assertTrue(result["compacted"])
        self.assertEqual(result["documents"], 3)
        self.assertEqual(result["bodies"], 2)
        self.assertEqual(result["index_sets"], 2)
        with self.store.connection() as db:
            relations = db.execute(
                "SELECT c.relname,c.relkind FROM pg_class c "
                "WHERE c.oid IN ('native_catalog_documents'::regclass,'native_catalog_records'::regclass)"
            ).fetchall()
            views = db.execute(
                "SELECT 'native_catalog_legacy_rows'::regclass::oid AS rows_oid,"
                "'native_catalog_legacy_nested'::regclass::oid AS nested_oid"
            ).fetchone()
            grants = db.execute(
                "SELECT EXISTS(SELECT 1 FROM aclexplode(c.relacl) x WHERE x.grantee=0 "
                "AND x.privilege_type='SELECT') AS public_select "
                "FROM pg_class c WHERE c.oid='native_catalog_legacy_rows'::regclass"
            ).fetchone()
            links = db.execute(
                "SELECT revision,path,body_id,index_set_id FROM native_catalog_document_links "
                "WHERE revision=ANY(%s) ORDER BY revision,path",
                ([revision_a, revision_b],),
            ).fetchall()
            bodies = db.execute(
                "SELECT revision,path,raw,sha256,source_bytes FROM native_catalog_documents "
                "WHERE revision=ANY(%s) ORDER BY revision,path",
                ([revision_a, revision_b],),
            ).fetchall()
            payloads = db.execute(
                "SELECT revision,path,payload::text AS payload FROM native_catalog_records "
                "WHERE revision=ANY(%s) ORDER BY revision,path",
                ([revision_a, revision_b],),
            ).fetchall()
        self.assertEqual({row["relkind"] for row in relations}, {"v"})
        self.assertEqual(views["rows_oid"], old_views["rows_oid"])
        self.assertEqual(views["nested_oid"], old_views["nested_oid"])
        self.assertTrue(grants["public_select"])
        link_map = {(row["revision"], row["path"]): row for row in links}
        self.assertEqual(
            link_map[(revision_a, "a.json")]["body_id"],
            link_map[(revision_b, "a.json")]["body_id"],
        )
        self.assertNotEqual(
            link_map[(revision_a, "a.json")]["body_id"],
            link_map[(revision_a, "b.json")]["body_id"],
        )
        self.assertEqual(
            link_map[(revision_a, "a.json")]["index_set_id"],
            link_map[(revision_a, "b.json")]["index_set_id"],
        )
        self.assertNotEqual(
            link_map[(revision_a, "a.json")]["index_set_id"],
            link_map[(revision_b, "a.json")]["index_set_id"],
        )
        self.assertEqual(
            {(row["path"], bytes(row["raw"])) for row in bodies},
            {("a.json", raw_shared), ("b.json", raw_other)},
        )
        self.assertEqual(
            {(row["revision"], row["path"], row["payload"]) for row in payloads},
            {
                (revision_a, "a.json", "1"),
                (revision_a, "b.json", "1"),
                (revision_b, "a.json", "1.0"),
            },
        )

        with self.assertRaisesRegex(Exception, "Published native catalog is immutable"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE native_catalog_records SET payload='2'::jsonb "
                    "WHERE revision=%s AND path='a.json' AND collection='items' AND record_key='1'",
                    (revision_a,),
                )
        with self.assertRaisesRegex(Exception, "Published native catalog is immutable"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE native_catalog_documents SET raw=%s "
                    "WHERE revision=%s AND path='a.json'",
                    (b"{}", revision_a),
                )

        with self.store.connection() as db:
            revision_cow = "d" * 64
            db.execute(
                "INSERT INTO native_catalog_releases "
                "(revision,document_count,source_bytes,complete) VALUES(%s,1,%s,false)",
                (revision_cow, len(raw_shared)),
            )
            from wakfu_server.native_shared_storage import clone_documents

            clone_documents(db, revision_cow, revision_a, only_paths=("a.json",))
            db.execute(
                "UPDATE native_catalog_records SET payload='2'::jsonb "
                "WHERE revision=%s AND path='a.json' AND collection='items' AND record_key='1'",
                (revision_cow,),
            )
            after_cow = db.execute(
                "SELECT revision,path,index_set_id FROM native_catalog_document_links "
                "WHERE revision=ANY(%s) ORDER BY revision,path",
                ([revision_a, revision_b, revision_cow],),
            ).fetchall()
            changed_payloads = db.execute(
                "SELECT revision,path,payload::text AS payload FROM native_catalog_records "
                "WHERE revision=ANY(%s) ORDER BY revision,path",
                ([revision_a, revision_b, revision_cow],),
            ).fetchall()
        changed_links = {
            (row["revision"], row["path"]): row["index_set_id"] for row in after_cow
        }
        self.assertNotEqual(
            changed_links[(revision_cow, "a.json")],
            changed_links[(revision_a, "a.json")],
        )
        self.assertEqual(
            {
                (row["revision"], row["path"], row["payload"])
                for row in changed_payloads
            },
            {
                (revision_cow, "a.json", "2"),
                (revision_a, "a.json", "1"),
                (revision_a, "b.json", "1"),
                (revision_b, "a.json", "1.0"),
            },
        )

    def test_corrupt_legacy_source_rolls_back_before_public_view_cutover(self):
        from tools.compact_native_storage import compact

        self._legacy_layout(corrupt=True)
        with self.assertRaisesRegex(ValueError, "checksum/size mismatch"):
            compact(self.store.database)
        with self.store.connection() as db:
            kinds = db.execute(
                "SELECT c.relname,c.relkind FROM pg_class c "
                "WHERE c.oid IN ('native_catalog_documents'::regclass,'native_catalog_records'::regclass)"
            ).fetchall()
            bad = db.execute(
                "SELECT raw FROM native_catalog_documents WHERE path='a.json' "
                "ORDER BY revision LIMIT 1"
            ).fetchone()
            links = db.execute(
                "SELECT count(*) AS n FROM native_catalog_document_links"
            ).fetchone()["n"]
            bodies = db.execute(
                "SELECT count(*) AS n FROM native_catalog_bodies"
            ).fetchone()["n"]
        self.assertEqual({row["relkind"] for row in kinds}, {"r"})
        self.assertEqual(bytes(bad["raw"]), b'{"source": "corrupted"}\n')
        self.assertEqual(links, 0)
        self.assertEqual(bodies, 0)

    def test_retired_corrupt_index_is_archived_without_being_scanned(self):
        from tools.compact_native_storage import compact
        from tools.import_native_catalogs import release_revision

        revision_a, revision_b, raw_shared, _, _ = self._legacy_layout(
            valid_revisions=True
        )
        raw_new = b'{"source": "new"}\n'
        revision_c = release_revision(
            [("new.json", hashlib.sha256(raw_new).hexdigest(), len(raw_new))]
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE native_catalog_releases SET created_at=now()-interval '3 days' "
                "WHERE revision=%s",
                (revision_a,),
            )
            db.execute(
                "UPDATE native_catalog_releases SET created_at=now()-interval '1 day' "
                "WHERE revision=%s",
                (revision_b,),
            )
            db.execute(
                "INSERT INTO native_catalog_releases "
                "(revision,document_count,source_bytes,complete) VALUES(%s,1,%s,false)",
                (revision_c, len(raw_new)),
            )
            db.execute(
                "INSERT INTO native_catalog_documents "
                "(revision,path,raw,sha256,source_bytes,record_count) "
                "VALUES(%s,'new.json',%s,%s,%s,1)",
                (
                    revision_c,
                    raw_new,
                    hashlib.sha256(raw_new).hexdigest(),
                    len(raw_new),
                ),
            )
            db.execute(
                "INSERT INTO native_catalog_records "
                "(revision,path,collection,record_key,payload) "
                "VALUES(%s,'new.json','items','1','1'::jsonb)",
                (revision_c,),
            )
            db.execute(
                "UPDATE native_catalog_releases SET complete=true WHERE revision=%s",
                (revision_c,),
            )
            db.execute(
                "DELETE FROM native_catalog_records WHERE revision=%s AND path='a.json'",
                (revision_a,),
            )
            from tools.compact_native_catalog import plan_retention

            _, _, planned_retired = plan_retention(db)
            self.assertEqual(planned_retired, [revision_a])
            retained_counts = db.execute(
                "SELECT d.revision,d.path,d.record_count,count(r.record_key) AS actual "
                "FROM native_catalog_documents d LEFT JOIN native_catalog_records r "
                "USING(revision,path) WHERE d.revision<>%s "
                "GROUP BY d.revision,d.path,d.record_count ORDER BY d.revision,d.path",
                (revision_a,),
            ).fetchall()
            self.assertTrue(
                all(row["record_count"] == row["actual"] for row in retained_counts),
                retained_counts,
            )
        result = compact(self.store.database)
        self.assertEqual(result["retired"], [revision_a])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_catalog_documents WHERE revision=%s",
                    (revision_a,),
                ).fetchone()["n"],
                0,
            )
            inventory = db.execute(
                "SELECT inventory FROM native_catalog_retired_inventories WHERE revision=%s",
                (revision_a,),
            ).fetchone()["inventory"]
        self.assertEqual(inventory["revision"], revision_a)

    def test_legacy_incomplete_release_preserves_unsealed_partial_index(self):
        from tools.compact_native_storage import compact

        revision_a, _, _, _, _ = self._legacy_layout()
        with self.store.connection() as db:
            db.execute(
                "UPDATE native_catalog_releases SET complete=false WHERE revision=%s",
                (revision_a,),
            )
            db.execute(
                "DELETE FROM native_catalog_records WHERE revision=%s AND path='a.json'",
                (revision_a,),
            )
        result = compact(self.store.database)
        self.assertTrue(result["compacted"])
        with self.store.connection() as db:
            partial = db.execute(
                "SELECT d.record_count,s.record_count AS actual,s.sealed "
                "FROM native_catalog_document_links d JOIN native_catalog_index_sets s USING(index_set_id) "
                "WHERE d.revision=%s AND d.path='a.json'",
                (revision_a,),
            ).fetchone()
            complete = db.execute(
                "SELECT complete FROM native_catalog_releases WHERE revision=%s",
                (revision_a,),
            ).fetchone()["complete"]
            logical_rows = db.execute(
                "SELECT count(*) AS n FROM native_catalog_records "
                "WHERE revision=%s AND path='a.json'",
                (revision_a,),
            ).fetchone()["n"]
        self.assertFalse(complete)
        self.assertEqual(partial["record_count"], 1)
        self.assertEqual(partial["actual"], 0)
        self.assertFalse(partial["sealed"])
        self.assertEqual(logical_rows, 0)

    def test_writer_role_can_only_write_through_canonical_views(self):
        from psycopg import sql

        role = "native_writer_" + uuid.uuid4().hex
        attack_view = "attacker_documents_" + uuid.uuid4().hex
        revision = "c" * 64
        with self.store.connection() as db:
            db.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
            self.addCleanup(self._drop_role, role)
            db.execute(
                "INSERT INTO native_catalog_releases(revision,document_count,source_bytes) "
                "VALUES(%s,1,2)",
                (revision,),
            )
            db.execute(
                sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                    sql.Identifier(
                        db.execute("SELECT current_schema() AS s").fetchone()["s"]
                    ),
                    sql.Identifier(role),
                )
            )
            db.execute(
                sql.SQL(
                    "GRANT INSERT,UPDATE,DELETE ON native_catalog_documents,native_catalog_records TO {}"
                ).format(sql.Identifier(role))
            )
            db.execute(
                sql.SQL(
                    "CREATE VIEW {} AS SELECT * FROM native_catalog_documents"
                ).format(sql.Identifier(attack_view))
            )
            db.execute(
                sql.SQL(
                    "CREATE TRIGGER attacker_writer INSTEAD OF INSERT ON {} "
                    "FOR EACH ROW EXECUTE FUNCTION write_native_shared_document()"
                ).format(sql.Identifier(attack_view))
            )
            db.execute(
                sql.SQL("GRANT INSERT ON {} TO {}").format(
                    sql.Identifier(attack_view), sql.Identifier(role)
                )
            )

        with self.store.connection() as db:
            db.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
            db.execute(
                "INSERT INTO native_catalog_documents "
                "(revision,path,raw,sha256,source_bytes,record_count) "
                "VALUES(%s,'safe.json',%s,%s,2,0)",
                (revision, b"{}", hashlib.sha256(b"{}").hexdigest()),
            )
            with self.assertRaises(Exception):
                with db.transaction():
                    db.execute(
                        "INSERT INTO native_catalog_bodies(sha256,raw,source_bytes) "
                        "VALUES(decode(repeat('00',32),'hex'),%s,0)",
                        (b"",),
                    )
            with self.assertRaisesRegex(Exception, "public view"):
                with db.transaction():
                    db.execute(
                        sql.SQL(
                            "INSERT INTO {}(revision,path,raw,sha256,source_bytes,record_count) "
                            "VALUES(%s,'attacker.json',%s,%s,2,0)"
                        ).format(sql.Identifier(attack_view)),
                        (revision, b"{}", hashlib.sha256(b"{}").hexdigest()),
                    )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_catalog_documents "
                    "WHERE revision=%s AND path='safe.json'",
                    (revision,),
                ).fetchone()["n"],
                1,
            )

    def _drop_role(self, role):
        from psycopg import sql

        with self.store.connection() as db:
            db.execute(sql.SQL("DROP OWNED BY {} CASCADE").format(sql.Identifier(role)))
            db.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
