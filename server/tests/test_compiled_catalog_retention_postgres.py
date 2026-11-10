"""Generation retention and reader pins in PostgresCase's disposable schema."""

import hashlib
import json
import tempfile
import uuid
from pathlib import Path

from postgres_case import PostgresCase


class CompiledCatalogRetentionPostgresTests(PostgresCase):
    def test_compatibility_writer_fails_fast_during_body_maintenance(self):
        with self.store.connection() as db:
            content_id = db.execute(
                "INSERT INTO native_compiled_collection_contents "
                "(collection,kind,representation,record_count,ordered_keys_sha256,records_sha256) "
                "VALUES('fixture.lock','dict','native_json',1,%s,%s) RETURNING content_id",
                ("a" * 64, "b" * 64),
            ).fetchone()["content_id"]
        from wakfu_server.storage.compiled_catalog_retention import MAINTENANCE_LOCK

        with self.store.connection() as maintenance:
            maintenance.execute(
                "SELECT pg_advisory_xact_lock(" + MAINTENANCE_LOCK + ")"
            )
            with self.assertRaisesRegex(Exception, "maintenance is active"):
                with self.store.connection() as writer:
                    writer.execute(
                        "INSERT INTO native_compiled_content_records "
                        "(content_id,record_key,ordinal,raw,sha256) VALUES(%s,'key',0,%s,%s)",
                        (content_id, b"body", hashlib.sha256(b"body").hexdigest()),
                    )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_compiled_record_bodies"
                ).fetchone()["n"],
                0,
            )

    def test_untrusted_writer_uses_only_compatibility_view(self):
        raw = b'{"value": 1}'
        checksum = hashlib.sha256(raw).hexdigest()
        writer = "compiled_view_writer_" + uuid.uuid4().hex[:10]
        with self.store.connection() as db:
            schema = db.execute("SELECT current_schema() AS schema").fetchone()[
                "schema"
            ]
            db.execute(f"CREATE ROLE {writer} NOLOGIN")
            db.execute(f"GRANT USAGE ON SCHEMA {schema} TO {writer}")
            db.execute(
                f"GRANT SELECT,INSERT,UPDATE ON native_compiled_content_records TO {writer}"
            )
            content_id = db.execute(
                "INSERT INTO native_compiled_collection_contents "
                "(collection,kind,representation,record_count,ordered_keys_sha256,records_sha256) "
                "VALUES('fixture.writer','dict','native_json',1,%s,%s) RETURNING content_id",
                ("a" * 64, "b" * 64),
            ).fetchone()["content_id"]
            db.execute(
                f"CREATE VIEW native_compiled_attacker AS SELECT content_id,record_key,ordinal,raw,sha256 "
                f"FROM native_compiled_content_records WHERE false"
            )
            db.execute(
                "CREATE TRIGGER attacker_writer INSTEAD OF INSERT ON native_compiled_attacker "
                "FOR EACH ROW EXECUTE FUNCTION write_native_compiled_content_record()"
            )
            db.execute(f"GRANT INSERT ON native_compiled_attacker TO {writer}")

        def drop_writer_role():
            with self.store.connection() as db:
                db.execute(f"DROP OWNED BY {writer}")
                db.execute(f"DROP ROLE {writer}")

        self.addCleanup(drop_writer_role)

        with self.store.connection() as db:
            db.execute(f"SET LOCAL ROLE {writer}")
            db.execute(
                "INSERT INTO native_compiled_content_records "
                "(content_id,record_key,ordinal,raw,sha256) VALUES(%s,'key',0,%s,%s)",
                (content_id, raw, checksum),
            )
        with self.assertRaisesRegex(Exception, "permission denied"):
            with self.store.connection() as db:
                db.execute(f"SET LOCAL ROLE {writer}")
                db.execute(
                    "INSERT INTO native_compiled_record_bodies(sha256,raw,source_bytes) "
                    "VALUES(decode(%s,'hex'),%s,%s)",
                    (checksum, raw, len(raw)),
                )
        with self.assertRaisesRegex(Exception, "unexpected relation"):
            with self.store.connection() as db:
                db.execute(f"SET LOCAL ROLE {writer}")
                db.execute(
                    "INSERT INTO native_compiled_attacker "
                    "(content_id,record_key,ordinal,raw,sha256) "
                    "VALUES(%s,'attack',0,%s,%s)",
                    (content_id, raw, checksum),
                )

        with self.store.connection() as db:
            db.execute(
                "UPDATE native_compiled_collection_contents SET complete=true "
                "WHERE content_id=%s",
                (content_id,),
            )
            before = db.execute(
                "SELECT count(*) AS n FROM native_compiled_record_bodies"
            ).fetchone()["n"]
        with self.assertRaisesRegex(Exception, "immutable"):
            with self.store.connection() as db:
                db.execute(f"SET LOCAL ROLE {writer}")
                changed_raw = b'{"value": 2}'
                db.execute(
                    "UPDATE native_compiled_content_records SET raw=%s,sha256=%s "
                    "WHERE content_id=%s AND record_key='key'",
                    (changed_raw, hashlib.sha256(changed_raw).hexdigest(), content_id),
                )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_compiled_record_bodies"
                ).fetchone()["n"],
                before,
            )

    def _legacy_records_table(self):
        with self.store.connection() as db:
            db.execute("DROP VIEW native_compiled_catalog_records")
            db.execute(
                "CREATE TABLE native_compiled_catalog_records ("
                "generation text NOT NULL,collection text NOT NULL,"
                "record_key text NOT NULL,ordinal integer NOT NULL,"
                "raw bytea NOT NULL,sha256 text NOT NULL,"
                "PRIMARY KEY(generation,collection,record_key),"
                "UNIQUE(generation,collection,ordinal))"
            )

    def test_compaction_keeps_two_recent_and_live_reader_then_prunes(self):
        from tools.compact_compiled_catalog import compact
        from wakfu_server.compiled_catalog_retention import prune_compiled_publications

        manifest = json.dumps({"collections": {}}, separators=(",", ":")).encode()
        source_revision = "a" * 64
        with self.store.connection() as db:
            # The current migration turns an empty legacy relation into the
            # compatibility view. Recreate the old relation here so this
            # test also exercises the explicit compaction path.
            db.execute("DROP VIEW native_compiled_catalog_records")
            db.execute(
                "CREATE TABLE native_compiled_catalog_records ("
                "generation text NOT NULL,collection text NOT NULL,"
                "record_key text NOT NULL,ordinal integer NOT NULL,"
                "raw bytea NOT NULL,sha256 text NOT NULL,"
                "PRIMARY KEY(generation,collection,record_key),"
                "UNIQUE(generation,collection,ordinal))"
            )
            db.execute(
                "INSERT INTO native_catalog_releases "
                "(revision,document_count,source_bytes,complete) VALUES(%s,0,0,true)",
                (source_revision,),
            )
            generations = []
            for index in range(4):
                raw = manifest + str(index).encode()
                generation = hashlib.sha256(raw).hexdigest()
                generations.append(generation)
                db.execute(
                    "INSERT INTO native_compiled_catalog_releases "
                    "(generation,policy,source_revision,source_inventory_sha256,"
                    "compiler_contract_sha256,config_sha256,manifest_raw,manifest,complete,created_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,false,"
                    "now()-(%s * interval '1 hour'))",
                    (
                        generation,
                        f"fixture-{index}",
                        source_revision,
                        "b" * 64,
                        "c" * 64,
                        "d" * 64,
                        raw,
                        manifest.decode(),
                        3 - index,
                    ),
                )
                db.execute(
                    "UPDATE native_compiled_catalog_releases SET complete=true "
                    "WHERE generation=%s",
                    (generation,),
                )

        # A second Database owns the session pin independently of pruning.
        from wakfu_server.storage.store import Store

        pin_store = Store(self.database_url)
        self.addCleanup(pin_store.close)
        pin_store.database.pin_compiled_generation(generations[0])

        compacted = compact(self.store.database, retain=2)
        self.assertTrue(compacted["compacted"])
        self.assertEqual(
            set(compacted["retained"]),
            {generations[0], generations[2], generations[3]},
        )
        with self.store.connection() as db:
            remaining = db.execute(
                "SELECT generation FROM native_compiled_catalog_releases"
            ).fetchall()
        self.assertEqual(
            {row["generation"] for row in remaining},
            {generations[0], generations[2], generations[3]},
        )

        pin_store.close()
        pruned = prune_compiled_publications(self.store.database, retain=2)
        self.assertEqual(pruned["removed"], [generations[0]])
        with self.store.connection() as db:
            remaining = db.execute(
                "SELECT generation FROM native_compiled_catalog_releases"
            ).fetchall()
        self.assertEqual(
            {row["generation"] for row in remaining},
            {generations[2], generations[3]},
        )

    def test_corrupt_legacy_content_aborts_compaction_without_dropping_source(self):
        from tools import publish_compiled_combat_catalog as publisher
        from tools.compact_compiled_catalog import compact

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        spool = publisher.PublicationSpool(
            str(Path(temporary.name) / "corrupt-spool.sqlite")
        )
        self.addCleanup(spool.db.close)
        metadata = spool.collection("fixture.records", {"key": {"value": 7}})
        source_revision = "e" * 64
        manifest = dict(
            policy="fixture",
            source_revision=source_revision,
            source_inventory_sha256="1" * 64,
            compiler_contract_sha256="2" * 64,
            config_sha256="3" * 64,
            collections=spool.collections,
        )
        raw_manifest = publisher.ordered_bytes(manifest)
        generation = hashlib.sha256(raw_manifest).hexdigest()
        with self.store.connection() as db:
            db.execute("DROP VIEW native_compiled_catalog_records")
            db.execute(
                "CREATE TABLE native_compiled_catalog_records ("
                "generation text NOT NULL,collection text NOT NULL,"
                "record_key text NOT NULL,ordinal integer NOT NULL,"
                "raw bytea NOT NULL,sha256 text NOT NULL,"
                "PRIMARY KEY(generation,collection,record_key),"
                "UNIQUE(generation,collection,ordinal))"
            )
            db.execute(
                "INSERT INTO native_catalog_releases "
                "(revision,document_count,source_bytes,complete) VALUES(%s,0,0,true)",
                (source_revision,),
            )
            db.execute(
                "INSERT INTO native_compiled_catalog_releases "
                "(generation,policy,source_revision,source_inventory_sha256,"
                "compiler_contract_sha256,config_sha256,manifest_raw,manifest,complete) "
                "VALUES(%s,'fixture',%s,%s,%s,%s,%s,%s::jsonb,false)",
                (
                    generation,
                    source_revision,
                    manifest["source_inventory_sha256"],
                    manifest["compiler_contract_sha256"],
                    manifest["config_sha256"],
                    raw_manifest,
                    raw_manifest.decode(),
                ),
            )
            db.execute(
                "INSERT INTO native_compiled_catalog_collections "
                "(generation,collection,kind,record_count,ordered_keys_raw,ordered_keys_sha256) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    generation,
                    metadata["collection"],
                    metadata["kind"],
                    metadata["count"],
                    spool.keys[metadata["collection"]],
                    metadata["ordered_keys_sha256"],
                ),
            )
            record_key, ordinal, record_raw, checksum = spool.db.execute(
                "SELECT record_key,ordinal,raw,sha256 FROM records"
            ).fetchone()
            db.execute(
                "INSERT INTO native_compiled_catalog_records "
                "(generation,collection,record_key,ordinal,raw,sha256) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    generation,
                    metadata["collection"],
                    record_key,
                    ordinal,
                    b"corrupt legacy bytes",
                    checksum,
                ),
            )
            db.execute(
                "UPDATE native_compiled_catalog_releases SET complete=true "
                "WHERE generation=%s",
                (generation,),
            )

        with self.assertRaisesRegex(ValueError, "Invalid compiled content"):
            compact(self.store.database)
        with self.store.connection() as db:
            relkind = db.execute(
                "SELECT relkind FROM pg_class WHERE oid=to_regclass('native_compiled_catalog_records')"
            ).fetchone()["relkind"]
            preserved = db.execute(
                "SELECT raw FROM native_compiled_catalog_records WHERE generation=%s",
                (generation,),
            ).fetchone()
            shared_count = db.execute(
                "SELECT count(*) AS n FROM native_compiled_collection_contents"
            ).fetchone()["n"]
        self.assertEqual(relkind, "r")
        self.assertEqual(bytes(preserved["raw"]), b"corrupt legacy bytes")
        self.assertEqual(shared_count, 0)
