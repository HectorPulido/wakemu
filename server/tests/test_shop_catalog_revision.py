"""Public cache invalidation follows committed PostgreSQL catalog mutations."""
from pathlib import Path
from postgres_case import PostgresCase
from wakfu_server.shop_cache import PublicCatalogCache
from wakfu_server.shop_domain import ShopService


class ShopCatalogRevisionTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.service = ShopService(self.store)
        self.service.public_cache = PublicCatalogCache(
            self.service.load_public_catalog, self.service.catalog_revision
        )
        with self.store.connection() as db:
            self.article_id = db.execute(
                "INSERT INTO shop_articles(key,name,item_ref,price_kamas,category) "
                "VALUES('revision-test','Revision test',2027,1000,'weapons') RETURNING id"
            ).fetchone()["id"]

    def test_direct_sql_price_and_visibility_changes_invalidate_warm_snapshot(self):
        initial = self.service.public_catalog()
        self.assertEqual(1000, self.own_article(initial)["price_kamas"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE shop_articles SET price_kamas=2600 WHERE id=%s",
                (self.article_id,),
            )
        updated = self.service.public_catalog()
        self.assertGreater(updated["revision"], initial["revision"])
        self.assertEqual(2600, self.own_article(updated)["price_kamas"])
        with self.store.connection() as db:
            db.execute("UPDATE shop_categories SET enabled=false WHERE key='weapons'")
        hidden = self.service.public_catalog()
        self.assertNotIn(self.article_id, {row["id"] for row in hidden["articles"]})
        self.assertNotIn("weapons", {row["key"] for row in hidden["categories"]})

    def test_rolled_back_update_does_not_replace_public_prices(self):
        before = self.service.public_catalog()
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE shop_articles SET price_kamas=9000 WHERE id=%s",
                    (self.article_id,),
                )
                raise RuntimeError("rollback")
        after = self.service.public_catalog()
        self.assertEqual(before["revision"], after["revision"])
        self.assertEqual(1000, self.own_article(after)["price_kamas"])

    def test_deleted_article_is_removed_from_cached_catalog(self):
        before = self.service.public_catalog()
        self.assertEqual(self.article_id, self.own_article(before)["id"])
        with self.store.connection() as db:
            db.execute("DELETE FROM shop_articles WHERE id=%s", (self.article_id,))
        self.assertNotIn(
            self.article_id,
            {row["id"] for row in self.service.public_catalog()["articles"]},
        )

    def own_article(self, snapshot):
        return next(row for row in snapshot["articles"] if row["id"] == self.article_id)

    def test_reapplying_bootstrap_preserves_revision_and_invalidation(self):
        before = self.service.public_catalog()
        migration = (
            Path(__file__).resolve().parents[1]
            / "migrations/130_shop_catalog_revision.sql"
        )
        with self.store.connection() as db:
            db.execute(migration.read_text(), prepare=False)
        self.assertEqual(before["revision"], self.service.catalog_revision())
        with self.store.connection() as db:
            db.execute(
                "UPDATE shop_articles SET enabled=false WHERE id=%s", (self.article_id,)
            )
        self.assertGreater(self.service.catalog_revision(), before["revision"])
        self.assertNotIn(
            self.article_id,
            {row["id"] for row in self.service.public_catalog()["articles"]},
        )
