"""Buyer quotes use fresh read-only prices and a separate eligibility gate."""
import csv
import json
import os
from pathlib import Path
import re
import sys
import threading
import types
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from wakfu_server.api import serve_api
from wakfu_server.bots.bridge import BotWorldBridge
from wakfu_server.bots.buyer_catalog import purchase_prices

BOT_SERVICE = Path(__file__).resolve().parents[1] / "bot-service"
if str(BOT_SERVICE) not in sys.path:
    sys.path.insert(0, str(BOT_SERVICE))
from wakfu_bots.clients import BuyerPriceClient, JsonClient


TOKEN = "dedicated-buyer-test-credential-123456"


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return self.rows


class FakeStore:
    def __init__(self, rows):
        self.db = FakeDB(rows)

    class Connection:
        def __init__(self, db):
            self.db = db

        def __enter__(self):
            return self.db

        def __exit__(self, *_):
            return False

    def connection(self):
        return self.Connection(self.db)


def patch_eligibility(mapping):
    module = types.ModuleType("wakfu_server.exchange_rules")

    def eligibility(reference):
        result = mapping.get(reference, "unknown")
        if result == "unknown":
            raise ValueError("Unknown native exchange item reference")
        return result

    module.eligibility = eligibility
    return patch.dict(sys.modules, {"wakfu_server.exchange_rules": module})


class BuyerCatalogTests(unittest.TestCase):
    def test_query_is_read_only_and_separates_buyer_eligibility_from_public_sale(self):
        store = FakeStore(
            [
                {"item_ref": 2865, "quantity": 8, "price_kamas": 230400},
                {"item_ref": 12, "quantity": 1, "price_kamas": 61000},
                {"item_ref": 1769, "quantity": 1, "price_kamas": 100},
                {"item_ref": 999999, "quantity": 1, "price_kamas": 1},
            ]
        )
        with patch_eligibility({2865: True, 12: True, 1769: False}):
            result = purchase_prices(store, [2865, 12, 1769, 999999])
        self.assertEqual(
            result["prices"],
            [
                {"reference": 2865, "quantity": 8, "price_kamas": 230400},
                {"reference": 12, "quantity": 1, "price_kamas": 61000},
            ],
        )
        self.assertEqual(len(store.db.calls), 2)
        self.assertEqual(store.db.calls[0], ("SET TRANSACTION READ ONLY", None))
        query, params = store.db.calls[1]
        self.assertIn("a.buyer_enabled OR (a.enabled AND c.enabled)", query)
        self.assertEqual(params, ([2865, 12, 1769, 999999],))
        self.assertNotRegex(query.upper(), r"\b(INSERT|UPDATE|DELETE)\b")

    def test_catalog_rejects_duplicates_bad_references_and_oversized_requests_before_db(
        self,
    ):
        store = FakeStore([])
        for refs in (
            [],
            [1, 1],
            [True],
            [0],
            [-1],
            [1.0],
            list(range(1, 130)),
            None,
        ):
            with self.subTest(refs=repr(refs)), self.assertRaises(ValueError):
                purchase_prices(store, refs)
        self.assertEqual(store.db.calls, [])

    def test_curated_migration_matches_exact_source_classes_and_leaves_holds_out(self):
        repo_root = Path(__file__).resolve().parents[2]
        server_root = Path(__file__).resolve().parents[1]
        migration_path = Path(
            os.environ.get(
                "WAKFU_BUYER_MIGRATION_PATH",
                server_root / "migrations/332_shop_buyer_eligibility.sql",
            )
        )
        csv_path = Path(
            os.environ.get(
                "WAKFU_BUYER_SOURCE_CSV",
                repo_root
                / "agents_docs/reports/item-pricing-20261011/deduplication/catalog.csv",
            )
        )
        if not migration_path.exists() or not csv_path.exists():
            self.skipTest("Curated buyer source CSV is not mounted in this test image")
        sql = migration_path.read_text()
        match = re.search(
            r"UPDATE shop_articles SET buyer_enabled=true WHERE item_ref IN \((.*?)\);",
            sql,
            re.S,
        )
        self.assertIsNotNone(match)
        migrated = {int(value) for value in re.findall(r"\d+", match.group(1))}
        with csv_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        curated = {
            int(row["reference"])
            for row in rows
            if row["disabled_reason"] == "lower_priority_same_name_and_type"
        }
        holds = {
            int(row["reference"])
            for row in rows
            if row["disabled_reason"]
            and row["disabled_reason"] != "lower_priority_same_name_and_type"
        }
        self.assertEqual(len(curated), 5282)
        self.assertEqual(len(holds), 1769)
        self.assertEqual(migrated, curated)
        self.assertTrue(migrated.isdisjoint(holds))
        self.assertIn(2865, migrated)


class BuyerPriceClientTests(unittest.TestCase):
    def test_fresh_quotes_use_minimum_duplicate_unit_price_and_exact_rounding(self):
        class HTTP:
            def __init__(self):
                self.calls = []
                self.responses = [
                    {
                        "prices": [
                            {"reference": 2865, "quantity": 8, "price_kamas": 230400},
                            {"reference": 2865, "quantity": 3, "price_kamas": 81000},
                            {"reference": 12, "quantity": 2, "price_kamas": 61000},
                        ]
                    },
                    {
                        "prices": [
                            {"reference": 2865, "quantity": 1, "price_kamas": 27000},
                            {"reference": 12, "quantity": 1, "price_kamas": 100},
                        ]
                    },
                ]

            def request(self, method, path, body):
                self.calls.append((method, path, body))
                return self.responses.pop(0)

        http = HTTP()
        buyer = BuyerPriceClient(http)
        items = [{"reference": 2865, "quantity": 2}, {"reference": 12, "quantity": 1}]
        self.assertEqual(buyer.quote(items, 80), 67600)
        self.assertEqual(
            http.calls[0],
            ("POST", "/internal/bots/buyer-prices", {"references": [2865, 12]}),
        )
        self.assertEqual(buyer.quote(items, 80), 43280)
        self.assertEqual(len(http.calls), 2)  # No stale price cache.

    def test_missing_price_returns_none_empty_offer_is_free_and_inputs_are_bounded(
        self,
    ):
        class HTTP:
            def __init__(self):
                self.calls = []

            def request(self, method, path, body):
                self.calls.append((method, path, body))
                return {"prices": []}

        http = HTTP()
        buyer = BuyerPriceClient(http)
        self.assertEqual(buyer.quote([], 80), 0)
        self.assertEqual(http.calls, [])
        self.assertIsNone(buyer.quote([{"reference": 2865, "quantity": 1}], 80))
        for items, percent in (
            ([{"reference": True, "quantity": 1}], 80),
            ([{"reference": 1, "quantity": 0}], 80),
            ([{"reference": 1, "quantity": 1}] * 129, 80),
            ([], True),
            ([], 101),
        ):
            with self.subTest(items=len(items), percent=percent), self.assertRaises(
                ValueError
            ):
                buyer.quote(items, percent)


class BuyerPriceBridgeTests(unittest.TestCase):
    def test_authenticated_world_route_returns_current_readonly_price_and_rejects_invalid_body(
        self,
    ):
        class Runtime:
            supported_actions = ()

            def __init__(self):
                self.store = FakeStore(
                    [{"item_ref": 2865, "quantity": 1, "price_kamas": 36000}]
                )

        bridge = BotWorldBridge(Runtime(), TOKEN)
        ready = threading.Event()
        servers = []
        thread = threading.Thread(
            target=serve_api,
            args=(object(), "127.0.0.1", 0),
            kwargs={
                "bots_bridge": bridge,
                "on_ready": lambda server: (servers.append(server), ready.set()),
            },
            daemon=True,
        )
        thread.start()
        self.assertTrue(ready.wait(2), "World API did not become ready")
        server = servers[0]
        base = f"http://127.0.0.1:{server.server_port}"

        def request(token, body):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = "Bearer " + token
            req = urllib.request.Request(
                base + "/internal/bots/buyer-prices",
                data=json.dumps(body).encode(),
                headers=headers,
                method="POST",
            )
            try:
                response = urllib.request.urlopen(req, timeout=3)
            except urllib.error.HTTPError as error:
                with error:
                    return error.code, json.load(error)
            with response:
                return response.code, json.load(response)

        try:
            with patch_eligibility({2865: True}):
                self.assertEqual(request(None, {"references": [2865]})[0], 401)
                buyer = BuyerPriceClient(JsonClient(base, TOKEN))
                self.assertEqual(
                    buyer.quote([{"reference": 2865, "quantity": 8}], 80), 230400
                )
                self.assertEqual(
                    request(TOKEN, {"references": [2865], "enabled": True})[0], 400
                )
                self.assertEqual(request(TOKEN, {"references": [2865, 2865]})[0], 400)
            self.assertEqual(Runtime.__name__, "Runtime")
            self.assertEqual(len(bridge.runtime.store.db.calls), 2)
            self.assertTrue(
                all(
                    call[0] == "SET TRANSACTION READ ONLY" or "SELECT" in call[0]
                    for call in bridge.runtime.store.db.calls
                )
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class BuyerPricePostgresTests(unittest.TestCase):
    """Run only on the dedicated, non-runtime PostgreSQL test database."""

    def setUp(self):
        from psycopg.conninfo import conninfo_to_dict, make_conninfo
        from wakfu_server.postgres import Database

        dsn = os.environ.get("WAKFU_POSTGRES_TEST_URL")
        if not dsn:
            self.skipTest("Dedicated PostgreSQL test database is not configured")
        database = conninfo_to_dict(dsn).get("dbname")
        if not database or database in {"wakemu", "wakemu_runtime"}:
            self.fail("Refusing buyer price integration test outside isolated database")
        password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        admin = Database(dsn, password_file=password_file)
        self.addCleanup(admin.close)
        schema = "buyer_case_" + __import__("uuid").uuid4().hex
        with admin.connection() as db:
            db.execute(f"CREATE SCHEMA {schema}")
        self.addCleanup(self._drop_schema, admin, schema)
        scoped_dsn = make_conninfo(dsn, options=f"-c search_path={schema}")
        self.store = Database(scoped_dsn, password_file=password_file)
        self.addCleanup(self.store.close)
        with self.store.connection() as db:
            db.execute(
                "CREATE TABLE shop_categories(key text PRIMARY KEY, enabled boolean NOT NULL)"
            )
            db.execute(
                "CREATE TABLE shop_articles("
                "id bigserial PRIMARY KEY,item_ref integer NOT NULL,quantity integer NOT NULL,"
                "price_kamas bigint NOT NULL,category text NOT NULL REFERENCES shop_categories(key),"
                "enabled boolean NOT NULL,buyer_enabled boolean NOT NULL)"
            )
            db.execute(
                "INSERT INTO shop_categories(key,enabled) VALUES('public',true),('hidden',false)"
            )
            db.execute(
                "INSERT INTO shop_articles(item_ref,quantity,price_kamas,category,enabled,buyer_enabled) "
                "VALUES(2865,1,36000,'public',true,false),"
                "(2865,8,288000,'hidden',false,true),"
                "(8050,1,999,'hidden',false,false),"
                "(9679,1,1,'public',false,false)"
            )

    @staticmethod
    def _drop_schema(admin, schema):
        with admin.connection() as db:
            db.execute(f"DROP SCHEMA {schema} CASCADE")

    def test_sql_buyer_only_duplicate_and_public_row_quote_without_visibility_changes(
        self,
    ):
        from wakfu_server.bots.buyer_catalog import purchase_prices

        def snapshot():
            with self.store.connection() as db:
                return (
                    db.execute(
                        "SELECT item_ref,quantity,price_kamas,category,enabled,buyer_enabled "
                        "FROM shop_articles ORDER BY id"
                    ).fetchall(),
                    db.execute(
                        "SELECT key,enabled FROM shop_categories ORDER BY key"
                    ).fetchall(),
                )

        before_articles, before_categories = snapshot()
        first = purchase_prices(self.store, [2865, 8050, 9679])
        self.assertEqual(
            first["prices"],
            [
                {"reference": 2865, "quantity": 1, "price_kamas": 36000},
                {"reference": 2865, "quantity": 8, "price_kamas": 288000},
            ],
        )

        class LiveHTTP:
            def request(_self, method, path, body):
                self.assertEqual(
                    (method, path), ("POST", "/internal/bots/buyer-prices")
                )
                return purchase_prices(self.store, body["references"])

        buyer = BuyerPriceClient(LiveHTTP())
        self.assertEqual(buyer.quote([{"reference": 2865, "quantity": 8}], 80), 230400)
        with self.store.connection() as db:
            db.execute(
                "UPDATE shop_articles SET price_kamas=CASE quantity "
                "WHEN 1 THEN 42000 WHEN 8 THEN 336000 END WHERE item_ref=2865"
            )
        self.assertEqual(buyer.quote([{"reference": 2865, "quantity": 8}], 80), 268800)
        after_articles, after_categories = snapshot()
        self.assertEqual(
            [
                (r["item_ref"], r["category"], r["enabled"], r["buyer_enabled"])
                for r in before_articles
            ],
            [
                (r["item_ref"], r["category"], r["enabled"], r["buyer_enabled"])
                for r in after_articles
            ],
        )
        self.assertEqual(before_categories, after_categories)
        self.assertEqual(
            [r for r in first["prices"] if r["reference"] == 2865],
            [
                {"reference": 2865, "quantity": 1, "price_kamas": 36000},
                {"reference": 2865, "quantity": 8, "price_kamas": 288000},
            ],
        )


if __name__ == "__main__":
    unittest.main()
