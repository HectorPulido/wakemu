"""Incremental raw-document reuse against shared PostgreSQL storage."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from tools import publish_compiled_combat_catalog as publisher
from wakfu_server.native_compiled_catalog import canonical_bytes


class RawDocumentReusePostgresTests(PostgresCase):
    def test_one_changed_document_reuses_only_unchanged_content(self):
        revision = "a" * 64
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_catalog_releases "
                "(revision,document_count,source_bytes,complete) VALUES(%s,0,0,true)",
                (revision,),
            )
        identity = {
            "policy": "raw-incremental-test",
            "source_revision": revision,
            "source_inventory_sha256": "b" * 64,
            "compiler_contract_sha256": "c" * 64,
            "config_sha256": "d" * 64,
            "source_documents": {"a.json": "1" * 64, "b.json": "2" * 64},
            "compiler_sources": {},
            "config": {},
        }
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)

        def make_spool(name):
            spool = publisher.PublicationSpool(str(Path(temp.name) / name))
            self.addCleanup(spool.db.close)
            return spool

        original = make_spool("original.sqlite")
        doc_a = {"effects": {"1": {"damage": 10}}}
        doc_b = {"states": {"2": {"level": 1}}}
        raw_a = dict(original.document("a.json", doc_a), source_sha256="1" * 64)
        raw_b = dict(original.document("b.json", doc_b), source_sha256="2" * 64)
        manifest = dict(
            identity,
            raw_documents={"a.json": raw_a, "b.json": raw_b},
            collections=original.collections,
        )
        with self.store.connection() as db:
            generation = publisher.publish(db, original, manifest, canonical_bytes)

        changed_identity = dict(
            identity,
            source_inventory_sha256="e" * 64,
            source_documents={"a.json": "3" * 64, "b.json": "2" * 64},
        )
        increment = make_spool("increment.sqlite")
        with patch("wakfu_server.native_catalog._database", return_value=self.store):
            reused = publisher.reuse_raw_document(increment, changed_identity, "b.json")
            self.assertEqual(reused, raw_b)
            self.assertIsNone(
                publisher.reuse_raw_document(increment, changed_identity, "a.json")
            )
            self.assertIsNone(
                publisher.reuse_raw_document(
                    make_spool("compiler.sqlite"),
                    dict(changed_identity, compiler_contract_sha256="f" * 64),
                    "b.json",
                )
            )
            self.assertIsNone(
                publisher.reuse_raw_document(
                    make_spool("config.sqlite"),
                    dict(changed_identity, config_sha256="f" * 64),
                    "b.json",
                )
            )
        new_a = dict(
            increment.document("a.json", {"effects": {"1": {"damage": 20}}}),
            source_sha256="3" * 64,
        )
        self.assertEqual(
            increment.db.execute("SELECT count(*) FROM records").fetchone()[0], 1
        )
        new_manifest = dict(
            changed_identity,
            raw_documents={"a.json": new_a, "b.json": reused},
            collections=increment.collections,
        )
        fresh = make_spool("fresh.sqlite")
        fresh_a = dict(
            fresh.document("a.json", {"effects": {"1": {"damage": 20}}}),
            source_sha256="3" * 64,
        )
        fresh_b = dict(fresh.document("b.json", doc_b), source_sha256="2" * 64)
        expected = dict(
            changed_identity,
            raw_documents={"a.json": fresh_a, "b.json": fresh_b},
            collections=fresh.collections,
        )
        self.assertEqual(canonical_bytes(new_manifest), canonical_bytes(expected))
        with self.store.connection() as db:
            statements = []

            class TracedDB:
                def execute(self, query, params=None):
                    statements.append(query)
                    return db.execute(query, params)

                def __getattr__(self, name):
                    return getattr(db, name)

            next_generation = publisher.publish(
                TracedDB(), increment, new_manifest, canonical_bytes
            )
            self.assertFalse(
                any(
                    "FROM native_compiled_catalog_records WHERE generation=" in query
                    for query in statements
                )
            )
            rows = db.execute(
                "SELECT generation,collection,content_id FROM native_compiled_catalog_collections "
                "WHERE generation=ANY(%s)",
                ([generation, next_generation],),
            ).fetchall()
        by_key = {
            (row["generation"], row["collection"]): row["content_id"] for row in rows
        }
        self.assertEqual(
            by_key[(generation, "documents.b.json.states")],
            by_key[(next_generation, "documents.b.json.states")],
        )
        self.assertNotEqual(
            by_key[(generation, "documents.a.json.effects")],
            by_key[(next_generation, "documents.a.json.effects")],
        )


if __name__ == "__main__":
    unittest.main()
