"""Native NPC authority is SQL-only and imported data preserves exact content."""
from contextlib import contextmanager
import gzip
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from wakfu_server.maps import (
    npc_catalog,
    npc_dialogue,
    npc_observed_dialogue,
    npc_objective_facts,
)


class FakeDatabase:
    def __init__(self, values):
        self.values = values
        self.queries = []
        self.name = None

    @contextmanager
    def connection(self):
        yield self

    def execute(self, query, params):
        self.queries.append((query, params))
        self.name = params[0]
        return self

    def fetchone(self):
        return (
            None if self.name not in self.values else {"value": self.values[self.name]}
        )


class NpcCatalogDatabaseTests(unittest.TestCase):
    def tearDown(self):
        for loader in (
            npc_dialogue.catalog,
            npc_observed_dialogue.ledger,
            npc_objective_facts.definitions,
        ):
            loader.cache_clear()

    def test_three_runtime_readers_use_sql_without_file_access(self):
        values = {
            "npc_dialogues": {"nodes": [{"id": 7, "choices": []}]},
            "npc_observed_dialogue_edges": {
                "schema": "native-observed-dialogue-edges-v1",
                "edges": [],
                "source_sha256": "a" * 64,
            },
            "npc_objective_definitions": {"objectives": [10, 20]},
        }
        database = FakeDatabase(values)
        self.tearDown()
        with patch.object(
            npc_catalog.native_catalog, "_database", return_value=database
        ), patch("builtins.open", side_effect=AssertionError("runtime file access")):
            self.assertEqual(npc_dialogue.catalog()["node_index"][7]["id"], 7)
            self.assertEqual(npc_observed_dialogue.ledger()["edges"], [])
            self.assertEqual(npc_objective_facts.definitions(), frozenset({10, 20}))
        self.assertEqual([params[0] for _, params in database.queries], list(values))
        self.assertTrue(
            all("SELECT value FROM settings" in query for query, _ in database.queries)
        )

    def test_missing_or_malformed_sql_catalog_fails_without_fallback(self):
        for values in ({}, {"npc_dialogues": []}):
            with self.subTest(values=values), patch.object(
                npc_catalog.native_catalog,
                "_database",
                return_value=FakeDatabase(values),
            ), patch("builtins.open", side_effect=AssertionError("file fallback")):
                with self.assertRaises(RuntimeError):
                    npc_catalog.document("npc_dialogues")
        with self.assertRaises(ValueError):
            npc_catalog.document("arbitrary_setting")

    def test_migration_preserves_all_three_import_artifacts_exactly(self):
        root = Path(__file__).resolve().parents[1]
        sql = (root / "migrations/153_native_npc_catalog_authority.sql").read_text()
        matches = re.findall(
            r"\('([^']+)',\$npcseed\$(.*?)\$npcseed\$::jsonb\)", sql, re.S
        )
        self.assertEqual(len(matches), 3)
        sources = {
            "npc_dialogues": "npc-dialogues",
            "npc_observed_dialogue_edges": "npc-observed-dialogue-edges",
            "npc_objective_definitions": "npc-objective-definitions",
        }
        self.assertEqual({name for name, _ in matches}, set(sources))
        for name, value in matches:
            with gzip.open(
                root / "protocol" / (sources[name] + ".json.gz"), "rt", encoding="utf-8"
            ) as source:
                self.assertEqual(json.loads(value), json.load(source))
        self.assertIn("ON CONFLICT (name) DO NOTHING", sql)
