"""Exact binary COPY equivalence after indexing an already compiled spool."""
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from psycopg import adapters
from psycopg.adapt import Transformer
from psycopg.pq import Format
from psycopg._copy_base import BinaryFormatter
from tools import publish_compiled_combat_catalog as publisher


class CompiledCatalogSpoolOrderTests(unittest.TestCase):
    def test_index_preserves_binary_stream_and_manifest_without_temporary_sort(self):
        candidate = os.environ.get("WAKFU_PUBLISHER_CANDIDATE")
        module = publisher
        if candidate:
            spec = importlib.util.spec_from_file_location(
                "candidate_publisher", candidate
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        spool = module.PublicationSpool(":memory:")
        self.addCleanup(spool.db.close)
        # Insertion order deliberately differs from encoded-key ordering.
        spool.collection(
            "z.mapping",
            {
                7: {"text": "niño ☃", "nested": [1, None]},
                "7": [True, -0.0],
                "a": {"z": 2, "a": 1},
            },
        )
        spool.collection("a.list", [{"snow": "雪"}, [1, "two"], None])
        spool.collection("empty", {})
        manifest = dict.fromkeys(
            (
                "policy",
                "source_revision",
                "source_inventory_sha256",
                "compiler_contract_sha256",
                "config_sha256",
            ),
            "0" * 64,
        )
        manifest["collections"] = copy.deepcopy(spool.collections)
        before_manifest = module.ordered_bytes(manifest)
        before_keys = copy.deepcopy(spool.keys)
        query = "SELECT collection,record_key,ordinal,raw,sha256 FROM records ORDER BY collection,ordinal"
        before_rows = spool.db.execute(query).fetchall()
        before_plan = spool.db.execute("EXPLAIN QUERY PLAN " + query).fetchall()
        self.assertTrue(any("TEMP B-TREE" in row[3] for row in before_plan))
        generation = hashlib.sha256(before_manifest).hexdigest()
        types = ["text", "text", "text", "int4", "bytea", "text"]

        def formatter():
            transformer = Transformer()
            transformer.set_dumper_types(
                [adapters.types.get_oid(t) for t in types], Format.BINARY
            )
            return BinaryFormatter(transformer)

        expected_formatter = formatter()
        expected = b"".join(
            bytes(expected_formatter.write_row((generation, *row)))
            for row in before_rows
        ) + bytes(expected_formatter.end())
        captured = []

        class BinaryCopy:
            def set_types(self, actual):
                if actual != types:
                    raise AssertionError(actual)
                self.formatter = formatter()

            def write_row(self, row):
                captured.append(bytes(self.formatter.write_row(row)))

        class Connection:
            def execute(self, sql, params=None):
                return SimpleNamespace(fetchone=lambda: {"n": len(before_rows)})

            def cursor(self):
                return self

            @contextmanager
            def copy(self, sql):
                instance = BinaryCopy()
                yield instance
                captured.append(bytes(instance.formatter.end()))

        with patch.object(module, "log") as log:
            actual_generation = module.publish(
                Connection(), spool, manifest, module.ordered_bytes
            )
        self.assertEqual(actual_generation, generation)
        self.assertEqual(b"".join(captured), expected)
        self.assertEqual(spool.db.execute(query).fetchall(), before_rows)
        self.assertEqual(module.ordered_bytes(manifest), before_manifest)
        self.assertEqual(spool.keys, before_keys)
        plan = spool.db.execute("EXPLAIN QUERY PLAN " + query).fetchall()
        self.assertFalse(any("TEMP B-TREE" in row[3] for row in plan))
        self.assertTrue(any("records_publication_order" in row[3] for row in plan))
        self.assertEqual(
            [call.args[0] for call in log.call_args_list],
            [
                "compiled_publication_spool_indexed",
                "compiled_publication_copied",
                "compiled_publication_analyzed",
            ],
        )
        self.assertEqual(log.call_args_list[1].kwargs["records"], len(before_rows))
        # IF NOT EXISTS is harmless when the same spool is exported again.
        captured.clear()
        with patch.object(module, "log"):
            self.assertEqual(
                module.publish(Connection(), spool, manifest, module.ordered_bytes),
                generation,
            )
        self.assertEqual(b"".join(captured), expected)
