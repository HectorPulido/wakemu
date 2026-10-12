"""DB-only boat authority, preserving the exact SQL import artifact."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server import native_boats
from postgres_case import PostgresCase


def seeded_document():
    sql = (
        Path(__file__).parents[1] / "migrations/154_native_boat_contract_authority.sql"
    ).read_text()
    return json.loads(sql.split("$native_boats$")[1])


def seeded_indexes():
    document = native_boats.validate(seeded_document())
    endpoints = {row["id"]: row for row in document["endpoints"]}
    links = {}
    for row in document["routes"]:
        links.setdefault(frozenset((row["source"], row["destination"])), []).append(row)
    return endpoints, links


class BoatCatalogTests(unittest.TestCase):
    def test_actual_loader_uses_only_setting_and_preserves_document(self):
        class Database:
            def execute(self, sql, args):
                self.query = (sql, args)
                return self

            def fetchone(self):
                return {"value": seeded_document()}

        db = Database()
        loaded = native_boats.load(db)
        self.assertEqual(loaded, seeded_document())
        self.assertEqual(
            db.query,
            ("SELECT value FROM settings WHERE name=%s", ("native_boat_contracts",)),
        )
        self.assertEqual((len(loaded["endpoints"]), len(loaded["routes"])), (87, 393))

    def test_missing_setting_fails_closed(self):
        class Database:
            def execute(self, *args):
                return self

            def fetchone(self):
                return None

        with self.assertRaisesRegex(ValueError, "Missing PostgreSQL"):
            native_boats.load(Database())

    def test_malformed_db_documents_rejected_without_partial_authority(self):
        bad = [None, {}, {"endpoints": [], "routes": [], "provenance": {}}]
        for mutate in (
            lambda d: d["endpoints"].append(copy.deepcopy(d["endpoints"][0])),
            lambda d: d["routes"][0].update(source=999999999),
            lambda d: d["routes"][0].update(id=True),
            lambda d: d["routes"][0].update(destination_criterion=None),
            lambda d: d["endpoints"][0]["source_position"].update(z=True),
            lambda d: d["routes"][0]["animation"].update(duration_ms=-1),
        ):
            document = seeded_document()
            mutate(document)
            bad.append(document)
        for document in bad:

            class Database:
                def execute(self, *args):
                    return self

                def fetchone(self):
                    return {"value": document}

            with self.subTest(document_type=type(document).__name__), self.assertRaises(
                ValueError
            ):
                native_boats.load(Database())

    def test_cached_runtime_loads_db_and_never_reads_packaged_file(self):
        class Database:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def connection(self):
                return self

            def execute(self, *args):
                return self

            def fetchone(self):
                return {"value": seeded_document()}

        native_boats._indexes.cache_clear()
        try:
            with patch(
                "wakfu_server.storage.native_catalog._database", return_value=Database()
            ), patch.object(
                Path, "read_bytes", side_effect=AssertionError("Filesystem fallback")
            ):
                self.assertEqual(len(native_boats._indexes()[0]), 87)
        finally:
            native_boats._indexes.cache_clear()


class BoatCatalogPostgresTests(PostgresCase):
    def test_migration_import_is_exact_and_runtime_loader_reads_postgres(self):
        with self.store.connection() as db:
            self.assertEqual(native_boats.load(db), seeded_document())
        native_boats._indexes.cache_clear()
        self.addCleanup(native_boats._indexes.cache_clear)
        with patch(
            "wakfu_server.storage.native_catalog._database", return_value=self.store
        ), patch.object(
            Path, "read_bytes", side_effect=AssertionError("Filesystem fallback")
        ):
            self.assertEqual(len(native_boats._indexes()[0]), 87)
            self.assertEqual(sum(map(len, native_boats._indexes()[1].values())), 393)

    def test_actual_database_missing_and_malformed_authority_fail_closed(self):
        from psycopg.types.json import Jsonb

        with self.store.connection() as db:
            db.execute("DELETE FROM settings WHERE name=%s", (native_boats.SETTING,))
            with self.assertRaisesRegex(ValueError, "Missing PostgreSQL"):
                native_boats.load(db)
            for document in (None, {}, dict(seeded_document(), routes=[])):
                db.execute(
                    "INSERT INTO settings(name,value) VALUES(%s,%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                    (native_boats.SETTING, Jsonb(document)),
                )
                with self.assertRaises(ValueError):
                    native_boats.load(db)

    def test_reapplying_seed_preserves_existing_database_authority(self):
        from psycopg.types.json import Jsonb

        document = seeded_document()
        document["provenance"]["authority_test"] = "preserved"
        sql = (
            Path(__file__).parents[1]
            / "migrations/154_native_boat_contract_authority.sql"
        ).read_text()
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (Jsonb(document), native_boats.SETTING),
            )
            db.execute(sql)
            self.assertEqual(native_boats.load(db), document)
