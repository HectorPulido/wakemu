"""Combat variants are reused together only for independent item sources."""
import copy
import hashlib
import json
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from tools import reuse_compiled_variants as reuse


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class Result:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value

    def fetchall(self):
        return self.value


class VariantReuseTests(unittest.TestCase):
    def setUp(self):
        self.previous = dict(
            policy="p",
            compiler_contract_sha256="c",
            config_sha256="x",
            config={"rift_native_gameplay_policy": None},
            source_documents={
                "item-exchange-metadata.json": "old",
                "spell-effect-trees.json": "same",
            },
        )
        self.current = copy.deepcopy(self.previous)
        self.current["source_documents"]["item-exchange-metadata.json"] = "new"
        keys = b'["1"]'
        key_hash = hashlib.sha256(keys).hexdigest()
        variants = {
            name: {
                kind: f"{name}.{kind}"
                for kind in ("source_effects", "effects", "entry_effects")
            }
            for name in ("player", "npc_imported", "npc_baseline", "weapon")
        }
        names = {"shared.states", "shared.state_effects"}
        names.update(
            value for variant in variants.values() for value in variant.values()
        )
        collections = {
            name: dict(
                collection=name,
                kind="dict",
                count=1,
                representation="native_json",
                ordered_keys_sha256=key_hash,
                records_sha256="records",
            )
            for name in names
        }
        self.previous.update(
            variants=variants,
            original_output_index={name: [] for name in variants},
            states="shared.states",
            state_effects="shared.state_effects",
            collections=collections,
        )
        raw = canonical(self.previous)
        self.candidate = dict(
            generation=hashlib.sha256(raw).hexdigest(),
            manifest_raw=raw,
            manifest=self.previous,
        )
        self.rows = [
            dict(
                collection=name,
                kind="dict",
                record_count=1,
                ordered_keys_raw=keys,
                ordered_keys_sha256=key_hash,
                complete=True,
                content_collection=name,
                content_kind="dict",
                representation="native_json",
                content_count=1,
                content_keys_sha256=key_hash,
                records_sha256="records",
            )
            for name in names
        ]
        self.spool = SimpleNamespace(collections={}, keys={})
        self.queries = []

    def run_reuse(self):
        test = self

        class DB:
            def execute(self, query, params=None):
                test.queries.append(query)
                if "pg_class" in query:
                    return Result({"relkind": "v"})
                if "native_compiled_catalog_releases" in query:
                    return Result([test.candidate])
                if "native_compiled_catalog_collections" in query:
                    return Result(test.rows)
                raise AssertionError(query)

        @contextmanager
        def connection():
            yield DB()

        with patch(
            "wakfu_server.native_catalog._database",
            return_value=SimpleNamespace(connection=connection),
        ), patch(
            "wakfu_server.native_compiled_catalog.canonical_bytes",
            side_effect=canonical,
        ):
            return reuse.reuse(self.spool, self.current)

    def test_all_variants_reused_without_loading_effect_records(self):
        result = self.run_reuse()
        self.assertEqual(result["variants"], self.previous["variants"])
        self.assertEqual(len(self.spool.collections), 14)
        self.assertFalse(
            any(
                "FROM native_compiled_catalog_records" in query
                for query in self.queries
            )
        )

    def test_changed_effect_config_or_compiler_blocks_reuse(self):
        for key in ("compiler_contract_sha256", "config_sha256"):
            other = copy.deepcopy(self.current)
            other[key] = "changed"
            self.assertFalse(reuse.compatible(self.previous, other))
        other = copy.deepcopy(self.current)
        other["source_documents"]["spell-effect-trees.json"] = "different"
        self.assertFalse(reuse.compatible(self.previous, other))
        other = copy.deepcopy(self.current)
        other["config"] = self.previous["config"] = {
            "policy": '{"source_document":"item-exchange-metadata.json"}'
        }
        self.assertFalse(reuse.compatible(self.previous, other))

    def test_incomplete_content_falls_back_without_partial_spool(self):
        self.rows[-1]["complete"] = False
        self.assertIsNone(self.run_reuse())
        self.assertEqual(self.spool.collections, {})


if __name__ == "__main__":
    unittest.main()
