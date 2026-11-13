"""Unchanged raw documents reuse sealed collections without reading records."""
import hashlib
import json
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from tools import publish_compiled_combat_catalog as publisher


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class Result:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value

    def fetchall(self):
        return self.value


class Database:
    def __init__(self, candidate, rows):
        self.candidate = candidate
        self.rows = rows
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))
        if "pg_class" in query:
            return Result({"relkind": "v"})
        if "native_compiled_catalog_releases" in query:
            if "manifest_raw,manifest" in query:
                return Result(self.candidate)
            return Result([self.candidate])
        if "native_compiled_catalog_collections" in query:
            return Result(self.rows)
        raise AssertionError(query)


class RawDocumentReuseTests(unittest.TestCase):
    def setUp(self):
        keys = b'["a"]'
        key_hash = hashlib.sha256(keys).hexdigest()
        self.meta = {
            "collection": "documents.spells.effects",
            "kind": "dict",
            "count": 1,
            "representation": "native_json",
            "ordered_keys_sha256": key_hash,
            "records_sha256": "record-digest",
        }
        self.entry = {
            "root_kind": "dict",
            "collections": {
                "effects": {
                    key: self.meta[key]
                    for key in ("collection", "kind", "count", "ordered_keys_sha256")
                }
            },
            "source_sha256": "same-source",
        }
        manifest = {
            "policy": "p",
            "compiler_contract_sha256": "compiler",
            "config_sha256": "config",
            "source_documents": {"spells.json": "same-source"},
            "raw_documents": {"spells.json": self.entry},
            "collections": {self.meta["collection"]: self.meta},
        }
        raw = canonical(manifest)
        self.candidate = {
            "generation": hashlib.sha256(raw).hexdigest(),
            "manifest_raw": raw,
            "manifest": manifest,
        }
        self.rows = [
            {
                "collection": self.meta["collection"],
                "kind": "dict",
                "record_count": 1,
                "ordered_keys_raw": keys,
                "ordered_keys_sha256": key_hash,
                "content_complete": True,
                "content_collection": self.meta["collection"],
                "content_kind": "dict",
                "representation": "native_json",
                "content_count": 1,
                "content_keys_sha256": key_hash,
                "records_sha256": "record-digest",
            }
        ]
        self.identity = {
            "policy": "p",
            "compiler_contract_sha256": "compiler",
            "config_sha256": "config",
            "source_documents": {"spells.json": "same-source"},
        }
        self.db = Database(self.candidate, self.rows)
        self.spool = SimpleNamespace(collections={}, keys={})

    def run_reuse(self, name="spells.json"):
        @contextmanager
        def connection():
            yield self.db

        with patch(
            "wakfu_server.native_catalog._database",
            return_value=SimpleNamespace(connection=connection),
        ), patch(
            "wakfu_server.native_compiled_catalog.canonical_bytes",
            side_effect=canonical,
        ):
            return publisher.reuse_raw_document(self.spool, self.identity, name)

    def test_same_source_reuses_keys_and_sealed_content_without_records(self):
        self.assertEqual(self.run_reuse(), self.entry)
        self.assertEqual(self.spool.collections[self.meta["collection"]], self.meta)
        self.assertEqual(self.spool.keys[self.meta["collection"]], b'["a"]')
        self.assertFalse(
            any(
                "native_compiled_catalog_records WHERE" in q for q, _ in self.db.queries
            )
        )
        release_query = next(
            (p for q, p in self.db.queries if "native_compiled_catalog_releases" in q)
        )
        self.assertEqual(
            release_query, ("p", "compiler", "config", "spells.json", "same-source")
        )

    def test_changed_source_or_corrupt_content_falls_back(self):
        self.identity["source_documents"]["spells.json"] = "changed"
        self.assertIsNone(self.run_reuse())
        self.identity["source_documents"]["spells.json"] = "same-source"
        self.rows[0]["content_complete"] = False
        self.assertIsNone(self.run_reuse())
        self.assertEqual(self.spool.collections, {})

    def test_conflicting_existing_alias_falls_back_without_mutation(self):
        self.spool.collections[self.meta["collection"]] = {"different": True}
        self.assertIsNone(self.run_reuse())
        self.assertEqual(
            self.spool.collections[self.meta["collection"]], {"different": True}
        )

    def test_matching_existing_alias_reuses_the_same_collection(self):
        self.spool.collections[self.meta["collection"]] = dict(self.meta)
        self.spool.keys[self.meta["collection"]] = b'["a"]'
        self.assertEqual(self.run_reuse(), self.entry)
        self.assertEqual(self.spool.keys[self.meta["collection"]], b'["a"]')

    def test_manifest_is_loaded_once_for_multiple_documents(self):
        manifest = self.candidate["manifest"]
        manifest["source_documents"]["second.json"] = "same-source"
        manifest["raw_documents"]["second.json"] = dict(self.entry)
        raw = canonical(manifest)
        self.candidate["manifest_raw"] = raw
        self.candidate["generation"] = hashlib.sha256(raw).hexdigest()
        self.identity["source_documents"]["second.json"] = "same-source"
        self.assertIsNotNone(self.run_reuse())
        self.assertIsNotNone(self.run_reuse("second.json"))
        self.assertEqual(
            sum("SELECT manifest_raw,manifest" in q for q, _ in self.db.queries), 1
        )


if __name__ == "__main__":
    unittest.main()
