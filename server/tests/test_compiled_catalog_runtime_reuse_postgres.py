"""PostgreSQL-backed aliasing of an AST-attested runtime-only source edit."""

import hashlib
import re
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from tools import compiled_runtime_attestations as attest
from tools import reuse_unchanged_compiled_catalog as reuse
from tools import publish_compiled_combat_catalog as publisher
from wakfu_server.storage.native_compiled_catalog import canonical_bytes


SOURCE = "wakfu_server/combat/combat_placement_policy.py"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class CompiledCatalogRuntimeReusePostgresTests(PostgresCase):
    def test_ast_sidecar_reuses_content_and_rejects_signature_or_compiler_changes(self):
        revision = "a" * 64
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_catalog_releases"
                "(revision,document_count,source_bytes,complete) VALUES(%s,0,0,true)",
                (revision,),
            )

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        server_root = root / "server"
        source_path = server_root / SOURCE
        source_path.parent.mkdir(parents=True)
        baseline_source = (
            b"CONSTANT = 3\n"
            b"def _arena(value):\n    return value + 1\n"
            b"def freeze(value):\n    return value\n"
            b"def compiler_entry():\n    return CONSTANT\n"
        )
        body_edit = baseline_source.replace(b"return value + 1", b"return value + 2")
        signature_edit = body_edit.replace(
            b"def _arena(value):", b"def _arena(value, extra=0):"
        )
        source_path.write_bytes(baseline_source)

        baseline = {
            "policy": "compiled-runtime-reuse-test-v1",
            "source_revision": revision,
            "source_inventory_sha256": "b" * 64,
            "compiler_contract_sha256": "c" * 64,
            "config_sha256": "d" * 64,
            "source_documents": {"fixture.json": "e" * 64},
            "compiler_sources": {SOURCE: sha(baseline_source)},
            "config": {"fixture": "stable"},
        }

        spool = publisher.PublicationSpool(str(root / "baseline.sqlite"))
        self.addCleanup(spool.db.close)
        spool.collection("fixture.effects", {"27": {"effect_class": 1}})
        spool.collection("fixture.states", {"5": {"effects": [27]}})
        manifest = dict(baseline, collections=spool.collections)
        with self.store.connection() as db:
            cold_started = time.perf_counter()
            generation = publisher.publish(db, spool, manifest, canonical_bytes)
            cold_seconds = time.perf_counter() - cold_started
            sidecar_count = attest.record_exact_publication(
                db, generation, manifest, server_root, canonical_bytes
            )
            self.assertEqual(sidecar_count, 1)
            recorded = db.execute(
                "SELECT source_sha256,policy_sha256,projection_sha256 "
                "FROM native_compiled_runtime_projections WHERE generation=%s AND source_path=%s",
                (generation, SOURCE),
            ).fetchone()
            self.assertEqual(recorded["source_sha256"], sha(baseline_source))
            source_record_count = db.execute(
                "SELECT count(*) AS n FROM native_compiled_catalog_records "
                "WHERE generation=%s",
                (generation,),
            ).fetchone()["n"]
            self.assertEqual(source_record_count, 2)

            source_path.write_bytes(body_edit)
            body_changed = dict(
                baseline,
                compiler_contract_sha256="f" * 64,
                compiler_sources={SOURCE: sha(body_edit)},
            )
            reuse_started = time.perf_counter()
            reuse_sql = []

            class TracedDB:
                def execute(self, query, params=None):
                    reuse_sql.append(query)
                    return db.execute(query, params)

            with patch.object(reuse, "__file__", str(server_root / "tools/reuse.py")):
                alias = reuse.try_reuse(TracedDB(), body_changed, canonical_bytes)
            reuse_seconds = time.perf_counter() - reuse_started
            self.assertIsNotNone(alias)
            self.assertNotEqual(alias, generation)
            old_content = db.execute(
                "SELECT content_id FROM native_compiled_catalog_collections "
                "WHERE generation=%s AND collection='fixture.effects'",
                (generation,),
            ).fetchone()["content_id"]
            new_content = db.execute(
                "SELECT content_id FROM native_compiled_catalog_collections "
                "WHERE generation=%s AND collection='fixture.effects'",
                (alias,),
            ).fetchone()["content_id"]
            self.assertEqual(new_content, old_content)
            record_table_read = re.compile(
                r"\b(?:FROM|JOIN)\s+(?:[\w\"]+\.)?"
                r"(?:native_compiled_catalog_records|native_compiled_content_records)\b",
                re.IGNORECASE,
            )
            self.assertFalse(
                any(record_table_read.search(query) for query in reuse_sql)
            )

            source_path.write_bytes(signature_edit)
            signature_changed = dict(
                body_changed,
                compiler_contract_sha256="1" * 64,
                compiler_sources={SOURCE: sha(signature_edit)},
            )
            with patch.object(reuse, "__file__", str(server_root / "tools/reuse.py")):
                self.assertIsNone(
                    reuse.try_reuse(db, signature_changed, canonical_bytes)
                )

            compiler_changed = dict(
                body_changed,
                compiler_contract_sha256="2" * 64,
                compiler_sources={
                    SOURCE: sha(body_edit),
                    "wakfu_server/combat/combat_spell.py": "3" * 64,
                },
            )
            source_path.write_bytes(body_edit)
            with patch.object(reuse, "__file__", str(server_root / "tools/reuse.py")):
                self.assertIsNone(
                    reuse.try_reuse(db, compiler_changed, canonical_bytes)
                )

        print(
            "CATALOG_REUSE_TIMING",
            {
                "cold_publish_seconds": cold_seconds,
                "ast_alias_seconds": reuse_seconds,
                "fixture_records": source_record_count,
                "reuse_metadata_queries": len(reuse_sql),
                "collections_aliased": len(spool.collections),
                "spool_used_for_alias": False,
            },
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
