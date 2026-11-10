"""Privacy boundary tests for normalized catalogs copied into a clean seed."""

import hashlib
import json
import os
import uuid
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

from postgres_case import PostgresCase


class CleanDatabaseBackupTests(PostgresCase):
    def test_copy_keeps_only_three_public_catalog_roles_and_fresh_admin(self):
        from tools.build_clean_database_backup import (
            add_admin,
            audit_clean_database,
            copy_native_catalogs,
            prepare_clean_state,
            validate_source_inventory,
        )
        from tools.import_native_catalogs import release_revision
        from wakfu_server.native_shared_storage import finalize_document, seal_release
        from wakfu_server.store import Store

        password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        password = (
            None if password_file is None else Path(password_file).read_text().strip()
        )
        base_url = os.environ["WAKFU_POSTGRES_TEST_URL"]
        base_database = conninfo_to_dict(base_url).get("dbname")
        if not base_database or base_database in {"wakemu", "wakemu_runtime"}:
            self.fail("Refusing a clean backup fixture against a runtime database")

        suffix = uuid.uuid4().hex[:12]
        source_name = "wakemu_clean_backup_test_src_" + suffix
        target_name = "wakemu_clean_backup_test_dst_" + suffix

        def drop_databases():
            with psycopg.connect(
                base_url,
                password=password,
                autocommit=True,
                row_factory=dict_row,
            ) as admin:
                for name in (target_name, source_name):
                    admin.execute(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname=%s AND pid<>pg_backend_pid()",
                        (name,),
                    )
                    admin.execute("DROP DATABASE IF EXISTS " + name)

        self.addCleanup(drop_databases)
        with psycopg.connect(
            base_url,
            password=password,
            autocommit=True,
            row_factory=dict_row,
        ) as admin:
            admin.execute("CREATE DATABASE " + source_name + " TEMPLATE template0")
            admin.execute("CREATE DATABASE " + target_name + " TEMPLATE template0")

        source_url = make_conninfo(
            base_url, dbname=source_name, options="-c search_path=public"
        )
        target_url = make_conninfo(
            base_url, dbname=target_name, options="-c search_path=public"
        )
        migrations = Path(
            os.environ.get(
                "WAKFU_MIGRATIONS_TEST_DIR",
                Path(__file__).resolve().parents[1] / "migrations",
            )
        )
        from wakfu_server.postgres import migrate

        with psycopg.connect(
            source_url, password=password, row_factory=dict_row
        ) as source, psycopg.connect(
            target_url, password=password, row_factory=dict_row
        ) as target:
            migrate(source, Path(migrations))
            migrate(target, Path(migrations))
            prepare_clean_state(target)
            for table in ("territory_weather", "ecology_dirty_scopes"):
                self.assertEqual(
                    target.execute(
                        "SELECT count(*) AS n FROM public." + table
                    ).fetchone()["n"],
                    0,
                )
            roles = {}
            native = {"active_revision": None, "releases": []}
            for role in ("active_revision", "mining_revision", "fishing_revision"):
                raw = ("public catalog fixture: " + role).encode()
                checksum = hashlib.sha256(raw).hexdigest()
                path = "public/" + role + ".json"
                revision = release_revision([(path, checksum, len(raw))])
                roles[role] = revision
                source.execute(
                    "INSERT INTO public.native_catalog_releases "
                    "(revision,document_count,source_bytes) VALUES(%s,1,%s)",
                    (revision, len(raw)),
                )
                source.execute(
                    "INSERT INTO public.native_catalog_documents "
                    "(revision,path,raw,sha256,source_bytes,record_count) "
                    "VALUES(%s,%s,%s,%s,%s,1)",
                    (revision, path, raw, checksum, len(raw)),
                )
                source.execute(
                    "INSERT INTO public.native_catalog_records "
                    "(revision,path,collection,record_key,payload) "
                    "VALUES(%s,%s,'fixture','1',%s::jsonb)",
                    (revision, path, json.dumps({"role": role})),
                )
                finalize_document(source, revision, path, count=1)
                seal_release(source, revision)
                source.execute(
                    "UPDATE public.native_catalog_releases SET complete=true "
                    "WHERE revision=%s",
                    (revision,),
                )
                native["releases"].append(
                    {
                        "revision": revision,
                        "document_count": 1,
                        "source_bytes": len(raw),
                        "complete": True,
                        "documents": [
                            {
                                "path": path,
                                "sha256": checksum,
                                "source_bytes": len(raw),
                            }
                        ],
                    }
                )
            native["active_revision"] = roles["active_revision"]
            source.execute(
                "INSERT INTO public.native_catalog_active(id,revision) VALUES(1,%s)",
                (roles["active_revision"],),
            )
            source_sets = source.execute(
                "SELECT d.revision,d.path,d.record_count,s.record_count AS indexed_count,"
                "s.sealed,s.records_sha256 FROM public.native_catalog_document_links d "
                "JOIN public.native_catalog_index_sets s USING(index_set_id) "
                "ORDER BY d.revision"
            ).fetchall()
            self.assertEqual(len(source_sets), 3)
            self.assertTrue(
                all(
                    row["record_count"] == row["indexed_count"]
                    and row["sealed"]
                    and row["records_sha256"] is not None
                    for row in source_sets
                ),
                source_sets,
            )

            private_raw = b'{"private":"excluded"}'
            private_path = "private/runtime.json"
            private_sha = hashlib.sha256(private_raw).hexdigest()
            private_revision = release_revision(
                [(private_path, private_sha, len(private_raw))]
            )
            source.execute(
                "INSERT INTO public.native_catalog_releases "
                "(revision,document_count,source_bytes) VALUES(%s,1,%s)",
                (private_revision, len(private_raw)),
            )
            source.execute(
                "INSERT INTO public.native_catalog_documents "
                "(revision,path,raw,sha256,source_bytes,record_count) "
                "VALUES(%s,%s,%s,%s,%s,1)",
                (
                    private_revision,
                    private_path,
                    private_raw,
                    private_sha,
                    len(private_raw),
                ),
            )
            source.execute(
                "INSERT INTO public.native_catalog_records "
                "(revision,path,collection,record_key,payload) "
                "VALUES(%s,%s,'fixture','private','{}'::jsonb)",
                (private_revision, private_path),
            )
            finalize_document(source, private_revision, private_path, count=1)
            seal_release(source, private_revision)
            source.execute(
                "UPDATE public.native_catalog_releases SET complete=true "
                "WHERE revision=%s",
                (private_revision,),
            )
            manifest = {"catalogs": roles}
            selected = validate_source_inventory(source, manifest, native)
            self.assertEqual(set(selected), set(roles.values()))
            copied = copy_native_catalogs(source, target, selected)
            self.assertEqual(copied["native_catalog_releases"], 3)
            self.assertEqual(add_admin(target), 1)
            audit = audit_clean_database(target, {"expected_counts": {}})
            self.assertEqual(audit["table_counts"]["accounts"], 1)
            self.assertEqual(audit["table_counts"]["characters"], 0)
            self.assertEqual(audit["table_counts"]["sessions"], 0)
            self.assertEqual(audit["table_counts"]["tokens"], 0)
            self.assertEqual(audit["table_counts"]["inventory_items"], 0)
            self.assertEqual(audit["table_counts"]["inventory_containers"], 0)
            starter_quest = target.execute(
                "SELECT account_id,reference,quantity FROM public.account_quest_items"
            ).fetchall()
            self.assertEqual(
                starter_quest,
                [{"account_id": 1, "reference": 32864, "quantity": 1}],
            )
            with target.transaction():
                target.execute(
                    "INSERT INTO public.account_quest_items(account_id,reference,quantity) "
                    "VALUES(1,99999,1)"
                )
                with self.assertRaisesRegex(ValueError, "starter entitlement"):
                    audit_clean_database(target, {"expected_counts": {}})
                target.execute(
                    "DELETE FROM public.account_quest_items "
                    "WHERE account_id=1 AND reference=99999"
                )
            copied_revisions = target.execute(
                "SELECT revision FROM public.native_catalog_releases ORDER BY revision"
            ).fetchall()
            self.assertEqual(
                {row["revision"] for row in copied_revisions}, set(roles.values())
            )
            self.assertNotIn(
                private_revision, {row["revision"] for row in copied_revisions}
            )
            self.assertEqual(
                target.execute(
                    "SELECT count(*) AS n FROM public.native_compiled_catalog_releases"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                target.execute(
                    "SELECT revision FROM public.native_catalog_active WHERE id=1"
                ).fetchone()["revision"],
                roles["active_revision"],
            )

        store = Store(target_url, password_file=password_file)
        self.addCleanup(store.close)
        self.assertEqual(
            store.authenticate("admin", "admin"), {"id": 1, "username": "admin"}
        )
