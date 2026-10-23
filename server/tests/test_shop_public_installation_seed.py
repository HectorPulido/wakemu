"""The reviewed public shop installs exactly and refuses operator overwrites."""
from pathlib import Path

import psycopg
from postgres_case import PostgresCase
from wakfu_server.shop_domain import ShopService


class PublicShopInstallationSeedTests(PostgresCase):
    def test_clean_catalog_reapply_and_operator_conflicts_preserve_disabled_native_item(
        self,
    ):
        seed = (
            Path(__file__).resolve().parents[1] / "seeds/shop_public_configuration.sql"
        ).read_text()
        with self.store.connection() as db:
            db.execute(seed)
            counts = db.execute(
                "SELECT count(*) AS total,count(*) FILTER(WHERE enabled) AS enabled "
                "FROM shop_articles"
            ).fetchone()
            categories = db.execute(
                "SELECT count(*) AS total,count(*) FILTER(WHERE enabled) AS enabled "
                "FROM shop_categories"
            ).fetchone()
            paused = db.execute(
                "SELECT key,quantity,price_kamas,category,enabled FROM shop_articles "
                "WHERE item_ref=11387"
            ).fetchall()
        self.assertEqual(dict(counts), {"total": 18816, "enabled": 11764})
        self.assertEqual(dict(categories), {"total": 12, "enabled": 11})
        self.assertEqual(len(paused), 1)
        self.assertEqual(
            tuple(
                paused[0][key]
                for key in ("quantity", "price_kamas", "category", "enabled")
            ),
            (1, 100, "resources", False),
        )
        service = ShopService(self.store)
        public = service.public_catalog()
        self.assertEqual(len(public["articles"]), 11764)
        self.assertFalse(any(row["item_ref"] == 11387 for row in public["articles"]))
        with self.store.connection() as db:
            db.execute(seed)
        self.assertEqual(service.public_catalog(), public)
        with self.store.connection() as db:
            extra = db.execute(
                "INSERT INTO shop_articles(key,name,item_ref,quantity,price_kamas,category,enabled) "
                "VALUES('operator-private-article','Operator choice',11387,1,17,'resources',false) RETURNING *"
            ).fetchone()
        with self.store.connection() as db:
            db.execute(seed)
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM shop_articles WHERE id=%s", (extra["id"],)
                    ).fetchone()
                ),
                dict(extra),
            )
            db.execute(
                "UPDATE shop_articles SET price_kamas=101 WHERE key=%s",
                (paused[0]["key"],),
            )
        changed_revision = service.catalog_revision()
        with self.assertRaisesRegex(
            psycopg.Error, "conflicts with existing operator configuration"
        ):
            with self.store.connection() as db:
                db.execute(seed)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT price_kamas FROM shop_articles WHERE key=%s",
                    (paused[0]["key"],),
                ).fetchone()["price_kamas"],
                101,
            )
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM shop_articles WHERE id=%s", (extra["id"],)
                    ).fetchone()
                ),
                dict(extra),
            )
        self.assertEqual(service.catalog_revision(), changed_revision)
