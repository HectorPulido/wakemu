"""Database-authoritative shop purchase tests in isolated PostgreSQL schemas."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.shop_domain import ShopService
from wakfu_server import shop_refresh
from wakfu_server.shop_http import ShopAdapter


class ShopPostgresTests(PostgresCase):
    def setUp(self):
        if os.environ.get("WAKFU_RUN_SHOP_POSTGRES_TESTS") != "1":
            self.skipTest(
                "Set WAKFU_RUN_SHOP_POSTGRES_TESTS=1 for isolated shop DB tests"
            )
        super().setUp()
        self.service = ShopService(self.store)
        self.account = self.store.register("shop_test_owner", "shop-test-password")[
            "id"
        ]
        self.character = self.store.create_character(
            self.account, "Shop Test Character"
        )
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.token = self.store.issue_token(
            self.account, "api", generation=self.generation
        )
        self.bag = next(
            entry["uid"]
            for entry in self.character["inventory_containers"]
            if entry["kind"] == 0
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=5000 WHERE account_id=%s",
                (self.account,),
            )
            self.article_id = db.execute(
                "INSERT INTO shop_articles(key,name,item_ref,quantity,price_kamas,category) "
                "VALUES('shop-test-hammer','Jalamartillo',2027,1,1000,'weapons') RETURNING id"
            ).fetchone()["id"]

    def wallet(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (self.account,)
            ).fetchone()["kamas"]

    def inventory(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT uid,reference,quantity FROM inventory_items WHERE character_id=%s ORDER BY uid",
                (self.character["id"],),
            ).fetchall()

    def order_count(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT count(*) AS n FROM shop_orders WHERE account_id=%s",
                (self.account,),
            ).fetchone()["n"]

    def test_purchase_debits_single_wallet_grants_item_and_replays_receipt(self):
        before_items = self.inventory()
        first = self.service.purchase(self.token, self.article_id, "cart-key-1")
        replay = self.service.purchase(self.token, self.article_id, "cart-key-1")

        self.assertEqual(first, replay)
        self.assertEqual(4000, self.wallet())
        self.assertEqual(len(before_items) + 1, len(self.inventory()))
        self.assertEqual(2027, first["item"]["reference"])
        self.assertEqual(1, first["item"]["quantity"])
        self.assertEqual(1, self.order_count())
        with self.assertRaisesRegex(ValueError, "different request"):
            self.service.purchase(self.token, self.article_id + 1, "cart-key-1")
        self.assertEqual(4000, self.wallet())

    def test_failed_inventory_grant_rolls_back_wallet_and_order(self):
        before_items = self.inventory()
        with patch(
            "wakfu_server.inventory_items.grant",
            side_effect=RuntimeError("grant failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "grant failed"):
                self.service.purchase(self.token, self.article_id, "grant-rollback")
        self.assertEqual(5000, self.wallet())
        self.assertEqual(before_items, self.inventory())
        self.assertEqual(0, self.order_count())

    def test_receipt_failure_rolls_back_wallet_and_grant(self):
        before_items = self.inventory()
        with patch.object(
            self.service, "_receipt", side_effect=RuntimeError("receipt failed")
        ):
            with self.assertRaisesRegex(RuntimeError, "receipt failed"):
                self.service.purchase(self.token, self.article_id, "receipt-rollback")
        self.assertEqual(5000, self.wallet())
        self.assertEqual(before_items, self.inventory())
        self.assertEqual(0, self.order_count())

    def test_insufficient_funds_does_not_grant_or_record_order(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=999 WHERE account_id=%s",
                (self.account,),
            )
        before_items = self.inventory()
        with self.assertRaisesRegex(ValueError, "Insufficient kamas"):
            self.service.purchase(self.token, self.article_id, "no-funds")
        self.assertEqual(999, self.wallet())
        self.assertEqual(before_items, self.inventory())
        self.assertEqual(0, self.order_count())

    def test_changed_price_from_native_cart_is_rejected_without_charge(self):
        before_items = self.inventory()
        with self.store.connection() as db:
            db.execute(
                "UPDATE shop_articles SET price_kamas=1200 WHERE id=%s",
                (self.article_id,),
            )
        with self.assertRaisesRegex(ValueError, "catalog price changed"):
            self.service.purchase(
                self.token, self.article_id, "stale-cart", expected_price=1000
            )
        self.assertEqual(5000, self.wallet())
        self.assertEqual(before_items, self.inventory())
        self.assertEqual(0, self.order_count())

    def test_game_token_is_not_accepted_as_shop_api_authentication(self):
        game_token = self.store.issue_token(
            self.account, "game", generation=self.generation
        )
        with self.assertRaises(PermissionError):
            self.service.balance(game_token)
        with self.assertRaises(PermissionError):
            self.service.purchase(game_token, self.article_id, "game-token")
        self.assertEqual(5000, self.wallet())
        self.assertEqual(0, self.order_count())

    def test_db_categories_are_sorted_and_drive_catalog_and_purchase_visibility(self):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO shop_categories(key,name,sort_order,enabled) VALUES"
                "('shop-test-live','Live test',25,true),('shop-test-hidden','Hidden test',26,false)"
            )
            live_article = db.execute(
                "INSERT INTO shop_articles(key,name,item_ref,quantity,price_kamas,category) "
                "VALUES('shop-test-live-item','Live test item',2027,1,1000,'shop-test-live') RETURNING id"
            ).fetchone()["id"]
            hidden_article = db.execute(
                "INSERT INTO shop_articles(key,name,item_ref,quantity,price_kamas,category) "
                "VALUES('shop-test-hidden-item','Hidden test item',2027,1,1000,'shop-test-hidden') RETURNING id"
            ).fetchone()["id"]

        categories = self.service.categories()
        self.assertEqual(
            sorted(categories, key=lambda row: (row["sort_order"], row["id"])),
            categories,
        )
        keys = [row["key"] for row in categories]
        self.assertIn("shop-test-live", keys)
        self.assertNotIn("shop-test-hidden", keys)
        visible_ids = {row["id"] for row in self.service.catalog()}
        self.assertIn(live_article, visible_ids)
        self.assertNotIn(hidden_article, visible_ids)

        adapter = ShopAdapter(self.service)
        prefix = "/en/shops/WAKFU_INGAME/"
        category_id = str(
            next(row["id"] for row in categories if row["key"] == "shop-test-live")
        )
        scoped = adapter.dispatch(
            "POST",
            prefix + "catalog-pages:get",
            {"category_id": category_id, "limit": 100},
            "",
        )
        self.assertEqual(
            [str(live_article)], [row["id"] for row in scoped["articles"]["values"]]
        )
        hidden_id = str(
            next(
                row["id"]
                for row in self._categories_including_disabled()
                if row["key"] == "shop-test-hidden"
            )
        )
        with self.assertRaises(LookupError):
            adapter.dispatch("GET", prefix + "categories/" + hidden_id, {}, "")
        with self.assertRaises(LookupError):
            adapter.dispatch(
                "POST", prefix + "catalog-pages:get", {"category_id": "999999"}, ""
            )

        with self.store.connection() as db:
            db.execute("UPDATE shop_categories SET enabled=false WHERE key='weapons'")
        visible_ids = {row["id"] for row in self.service.catalog()}
        self.assertNotIn(self.article_id, visible_ids)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.service.purchase(self.token, self.article_id, "disabled-category")
        self.assertEqual(5000, self.wallet())
        self.assertEqual(0, self.order_count())

    def _categories_including_disabled(self):
        with self.store.connection() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM shop_categories").fetchall()
            ]

    def test_full_inventory_rejects_before_debit(self):
        with self.store.connection() as db:
            containers = db.execute(
                "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s",
                (self.character["id"],),
            ).fetchall()
            for container in containers:
                for slot in range(container["capacity"]):
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                        "VALUES(%s,2021,1,%s,%s)",
                        (self.character["id"], container["uid"], slot),
                    )
        before_items = self.inventory()
        with self.assertRaisesRegex(ValueError, "Inventory full"):
            self.service.purchase(self.token, self.article_id, "full-inventory")
        self.assertEqual(5000, self.wallet())
        self.assertEqual(before_items, self.inventory())
        self.assertEqual(0, self.order_count())

    def test_concurrent_retry_key_has_one_charge_grant_and_receipt(self):
        barrier = threading.Barrier(2)

        def buy():
            barrier.wait(timeout=5)
            return self.service.purchase(self.token, self.article_id, "parallel-retry")

        with ThreadPoolExecutor(max_workers=2) as workers:
            receipts = list(workers.map(lambda _: buy(), range(2)))
        self.assertEqual(receipts[0], receipts[1])
        self.assertEqual(4000, self.wallet())
        self.assertEqual(
            1, len([item for item in self.inventory() if item["reference"] == 2027])
        )
        self.assertEqual(1, self.order_count())

    def test_stale_api_session_cannot_purchase_or_read_balance(self):
        self.store.begin_session(self.account)
        before_items = self.inventory()
        with self.assertRaises((PermissionError, ValueError)):
            self.service.purchase(self.token, self.article_id, "stale-session")
        with self.assertRaises((PermissionError, ValueError)):
            self.service.balance(self.token)
        self.assertEqual(5000, self.wallet())
        self.assertEqual(before_items, self.inventory())
        self.assertEqual(0, self.order_count())

    def test_pending_refresh_retries_until_acknowledged(self):
        receipt = self.service.purchase(self.token, self.article_id, "refresh-order")
        character = self.store.character(self.account, self.character["id"])
        first = shop_refresh.pending(self.store, self.account, character)
        self.assertEqual([receipt["order_id"]], first["order_ids"])
        self.assertEqual(4000, first["character"]["kamas"])
        # A failed send must leave the durable order eligible for another send.
        second = shop_refresh.pending(self.store, self.account, character)
        self.assertEqual(first["order_ids"], second["order_ids"])
        shop_refresh.acknowledge(
            self.store, self.account, self.character["id"], first["order_ids"]
        )
        self.assertIsNone(shop_refresh.pending(self.store, self.account, character))
