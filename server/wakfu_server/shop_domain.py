"""Database-authoritative shop purchases with one OG/kama wallet and receipts."""
import secrets


class ShopService:
    def __init__(self, store):
        self.store = store
        self.public_cache = None

    def catalog_revision(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT revision FROM shop_catalog_revision WHERE id=1"
            ).fetchone()["revision"]

    def load_public_catalog(self):
        # One MVCC snapshot binds both collections to the same invalidation revision.
        with self.store.connection() as db:
            db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            revision = db.execute(
                "SELECT revision FROM shop_catalog_revision WHERE id=1"
            ).fetchone()["revision"]
            categories = db.execute(
                "SELECT * FROM shop_categories WHERE enabled ORDER BY sort_order,id"
            ).fetchall()
            rows = db.execute(
                "SELECT a.* FROM shop_articles a JOIN shop_categories c ON c.key=a.category "
                "WHERE a.enabled AND c.enabled ORDER BY c.sort_order,c.id,a.id"
            ).fetchall()
        return {
            "revision": revision,
            "categories": [dict(row) for row in categories],
            "articles": [dict(row, item_id=row["item_ref"]) for row in rows],
        }

    def public_catalog(self):
        if self.public_cache is not None:
            return self.public_cache.get()
        return self.load_public_catalog()

    def _authenticate(self, db, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 512:
            raise PermissionError("Invalid shop authentication")
        row = db.execute(
            "SELECT t.account_id,t.generation,s.character_id FROM tokens t "
            "JOIN sessions s ON s.account_id=t.account_id AND s.generation=t.generation "
            "WHERE t.digest=%s AND t.kind='api' AND t.expires_at>%s AND s.expires_at>%s",
            (self.store.digest(token), self.store.now(), self.store.now()),
        ).fetchone()
        if row is None:
            raise PermissionError("Shop session expired; reconnect to the game")
        return dict(row)

    def authenticate(self, token):
        with self.store.connection() as db:
            return self._authenticate(db, token)

    def balance(self, token):
        with self.store.connection() as db:
            auth = self._authenticate(db, token)
            return db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s",
                (auth["account_id"],),
            ).fetchone()["kamas"]

    def categories(self):
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT * FROM shop_categories WHERE enabled ORDER BY sort_order,id"
            ).fetchall()
        return [dict(row) for row in rows]

    def catalog(self):
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT a.* FROM shop_articles a JOIN shop_categories c ON c.key=a.category WHERE a.enabled AND c.enabled ORDER BY c.sort_order,c.id,a.id"
            ).fetchall()
        return [dict(row, item_id=row["item_ref"]) for row in rows]

    @staticmethod
    def _receipt(row):
        return dict(
            order_id=row["id"],
            account_id=row["account_id"],
            character_id=row["character_id"],
            balance=row["balance"],
            article_id=row["article_id"],
            price_kamas=row["price_kamas"],
            item=dict(
                uid=row["item_uid"], reference=row["item_ref"], quantity=row["quantity"]
            ),
        )

    def purchase(self, token, article_id, request_key, *, expected_price=None):
        if type(article_id) is not int or article_id <= 0:
            raise ValueError("Invalid shop article")
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 200:
            raise ValueError("Invalid shop operation key")
        from wakfu_server.inventory_move import STACKS
        from wakfu_server.inventory_items import grant
        from wakfu_server.combat_drop_delivery import _container_can_hold

        with self.store.connection() as db:
            auth = self._authenticate(db, token)
            account = auth["account_id"]
            # Account lock serializes retries and purchases across characters.
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            auth = self._authenticate(db, token)
            prior = db.execute(
                "SELECT * FROM shop_orders WHERE account_id=%s AND request_key=%s",
                (account, request_key),
            ).fetchone()
            if prior is not None:
                if prior["article_id"] != article_id:
                    raise ValueError("Operation key belongs to a different request")
                return self._receipt(prior)
            character = auth["character_id"]
            if character is None:
                raise ValueError("Select a character before purchasing")
            self.store.lock_character(db, account, auth["generation"], character)
            if db.execute(
                "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
                (character,),
            ).fetchone():
                raise ValueError("Shop purchases are unavailable during combat")
            article = db.execute(
                "SELECT a.* FROM shop_articles a JOIN shop_categories c ON c.key=a.category WHERE a.id=%s AND a.enabled AND c.enabled FOR SHARE OF a,c",
                (article_id,),
            ).fetchone()
            if article is None:
                raise ValueError("Shop article is unavailable")
            if expected_price is not None and article["price_kamas"] != expected_price:
                raise ValueError("The catalog price changed; reopen the shop")
            rule = STACKS.get(article["item_ref"])
            if rule is None or article["quantity"] > min(rule["maximum"], 32767):
                raise ValueError("Shop article is outside the supported native catalog")
            bags = db.execute(
                "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY kind,uid",
                (character,),
            ).fetchall()
            occupied = {
                (r["container"], r["slot"])
                for r in db.execute(
                    "SELECT container,slot FROM inventory_items WHERE character_id=%s",
                    (character,),
                )
            }
            destination = next(
                (
                    (b["uid"], slot)
                    for b in bags
                    if _container_can_hold(b, character)
                    for slot in range(b["capacity"])
                    if (b["uid"], slot) not in occupied
                ),
                None,
            )
            if destination is None:
                raise ValueError("Inventory full; free one slot before purchasing")
            wallet = db.execute(
                "UPDATE account_wallets SET kamas=kamas-%s WHERE account_id=%s AND kamas>=%s RETURNING kamas",
                (article["price_kamas"], account, article["price_kamas"]),
            ).fetchone()
            if wallet is None:
                raise ValueError("Insufficient kamas (OG mirrors the same wallet)")
            item = grant(
                self.store,
                account,
                auth["generation"],
                character,
                reference=article["item_ref"],
                quantity=article["quantity"],
                container=destination[0],
                slot=destination[1],
                allowed_references=STACKS,
                db=db,
            )
            row = db.execute(
                "INSERT INTO shop_orders(id,account_id,character_id,request_key,article_id,item_uid,"
                "item_ref,quantity,price_kamas,balance) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    secrets.token_hex(16),
                    account,
                    character,
                    request_key,
                    article_id,
                    item["uid"],
                    article["item_ref"],
                    article["quantity"],
                    article["price_kamas"],
                    wallet["kamas"],
                ),
            ).fetchone()
            return self._receipt(row)
