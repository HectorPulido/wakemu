"""Audited administration without bypassing the world's session ownership."""
import re
import secrets
from psycopg.types.json import Jsonb
from . import admin_map_catalog, admin_profiler
from wakfu_server.admin_actions import AdminActions
from wakfu_server.account_bans import AccountBans
from wakfu_server.admin_settings import AdminSettings
from wakfu_server.admin_operations import AdminOperations


class AdminService(AdminActions, AdminSettings, AdminOperations, AccountBans):
    def __init__(self, store):
        self.store = store

    @staticmethod
    def page(limit=50, offset=0):
        limit, offset = int(limit), int(offset)
        if not 1 <= limit <= 100 or not 0 <= offset <= 1000000:
            raise ValueError("Invalid pagination")
        return limit, offset

    @staticmethod
    def integer(value, low, high, field):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"Invalid {field}")
        return value

    @staticmethod
    def text(value, field, maximum=200, empty=False):
        if (
            not isinstance(value, str)
            or len(value) > maximum
            or (not empty and not value.strip())
        ):
            raise ValueError(f"Invalid {field}")
        return value.strip()

    def _audit(self, db, operator, action, target, before, after):
        db.execute(
            "INSERT INTO admin_panel_audit(operator,action,target,before_data,after_data) VALUES(%s,%s,%s,%s,%s)",
            (
                operator,
                action,
                str(target),
                Jsonb(before) if before is not None else None,
                Jsonb(after) if after is not None else None,
            ),
        )

    def _list(self, db, sql, params, limit, offset):
        limit, offset = self.page(limit, offset)
        total = db.execute(
            "SELECT count(*) AS n FROM (" + sql + ") listed", params
        ).fetchone()["n"]
        rows = db.execute(
            sql + " LIMIT %s OFFSET %s", (*params, limit, offset)
        ).fetchall()
        return dict(
            items=[dict(r) for r in rows], total=total, limit=limit, offset=offset
        )

    def dashboard(self):
        with self.store.connection() as db:
            counts = db.execute(
                "SELECT (SELECT count(*) FROM accounts) accounts,(SELECT count(*) FROM characters) characters,(SELECT count(*) FROM sessions WHERE expires_at>now() AND character_id IS NOT NULL) online,(SELECT count(*) FROM combat_fights WHERE status IN ('placement','active')) active_fights"
            ).fetchone()
            online = db.execute(
                "SELECT s.account_id,a.username,s.character_id,c.name,c.level,c.map_id,c.instance_id,c.x,c.y,c.z,s.expires_at FROM sessions s JOIN accounts a ON a.id=s.account_id JOIN characters c ON c.id=s.character_id WHERE s.expires_at>now() ORDER BY a.username LIMIT 100"
            ).fetchall()
            recent_audit = [
                dict(r)
                for r in db.execute(
                    "SELECT id,operator,action,target,created_at FROM admin_panel_audit ORDER BY id DESC LIMIT 8"
                )
            ]
        from wakfu_server.admin_positions import present

        return dict(
            counts=dict(counts),
            online=present(self.store, online),
            recent_audit=recent_audit,
            presence_note="Active character session leases; disconnected sessions are removed normally. A server crash can leave leases visible until expiry (up to 300 seconds).",
        )

    ACCOUNT_SQL = "SELECT a.id,a.username,a.is_admin,a.created_at,EXISTS(SELECT 1 FROM account_bans b WHERE b.account_id=a.id AND (b.expires_at IS NULL OR b.expires_at>now())) banned,coalesce(w.kamas,0) kamas,(SELECT count(*) FROM characters c WHERE c.account_id=a.id) character_count,EXISTS(SELECT 1 FROM sessions s WHERE s.account_id=a.id AND s.expires_at>now()) online FROM accounts a LEFT JOIN account_wallets w ON w.account_id=a.id"

    def accounts(self, q="", limit=50, offset=0):
        with self.store.connection() as db:
            return self._list(
                db,
                self.ACCOUNT_SQL + " WHERE a.username ILIKE %s ORDER BY a.id DESC",
                ("%" + str(q)[:100] + "%",),
                limit,
                offset,
            )

    def account(self, account_id):
        with self.store.connection() as db:
            row = db.execute(
                self.ACCOUNT_SQL + " WHERE a.id=%s", (account_id,)
            ).fetchone()
            if row is None:
                raise LookupError("Account not found")
            result = dict(row)
            ban = db.execute(
                "SELECT reason,operator,banned_at,expires_at FROM account_bans WHERE account_id=%s",
                (account_id,),
            ).fetchone()
            result["ban"] = dict(ban) if ban else None
            result["characters"] = [
                dict(r)
                for r in db.execute(
                    "SELECT id,name,breed,level,hp,max_hp,map_id,instance_id,x,y,z FROM characters WHERE account_id=%s ORDER BY id",
                    (account_id,),
                )
            ]
            return result

    def _account_values(self, data, create=False):
        if not isinstance(data, dict) or set(data) - {
            "username",
            "password",
            "is_admin",
            "kamas",
        }:
            raise ValueError("Unsupported account field")
        values = dict(data)
        if create and not {"username", "password"} <= set(values):
            raise ValueError("Username and password required")
        if "username" in values:
            if not isinstance(values["username"], str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{3,32}", values["username"]
            ):
                raise ValueError(
                    "Username must contain 3–32 letters, numbers, underscores or hyphens"
                )
        if "password" in values and (
            not isinstance(values["password"], str)
            or not 8 <= len(values["password"]) <= 256
        ):
            raise ValueError("Password must contain 8–256 characters")
        if "is_admin" in values and type(values["is_admin"]) is not bool:
            raise ValueError("Invalid administrator flag")
        if "kamas" in values:
            self.integer(values["kamas"], 0, 2147483647, "kamas")
        return values

    def create_account(self, data, operator):
        values = self._account_values(data, True)
        salt = secrets.token_bytes(16)
        hashed = self.store.password_hash(values["password"], salt)
        with self.store.connection() as db:
            row = db.execute(
                "INSERT INTO accounts(username,username_key,salt,password_hash,is_admin) VALUES(%s,%s,%s,%s,%s) RETURNING id,username,is_admin",
                (
                    values["username"],
                    values["username"].casefold(),
                    salt,
                    hashed,
                    values.get("is_admin", False),
                ),
            ).fetchone()
            db.execute(
                "INSERT INTO account_wallets(account_id,kamas) VALUES(%s,%s)",
                (row["id"], values.get("kamas", 0)),
            )
            if values.get("is_admin", False):
                db.execute(
                    "INSERT INTO admin_role_audit(account_id,is_admin,operator,reason) VALUES(%s,%s,%s,%s)",
                    (row["id"], True, operator, "Admin panel account creation"),
                )
            self._audit(
                db,
                operator,
                "account.create",
                row["id"],
                None,
                dict(row, kamas=values.get("kamas", 0)),
            )
        return self.account(row["id"])

    def update_account(self, account_id, data, operator):
        values = self._account_values(data)
        if not values:
            raise ValueError("No account changes")
        with self.store.connection() as db:
            before = db.execute(
                "SELECT a.id,a.username,a.is_admin,w.kamas FROM accounts a JOIN account_wallets w ON w.account_id=a.id WHERE a.id=%s FOR UPDATE OF a,w",
                (account_id,),
            ).fetchone()
            if before is None:
                raise LookupError("Account not found")
            # begin_session locks this same account row, closing the login race.
            if db.execute(
                "SELECT 1 FROM sessions WHERE account_id=%s AND expires_at>now()",
                (account_id,),
            ).fetchone():
                raise ValueError(
                    "Account has an active session; disconnect it before editing"
                )
            for field in ("username", "is_admin"):
                if field in values:
                    db.execute(
                        "UPDATE accounts SET " + field + "=%s WHERE id=%s",
                        (values[field], account_id),
                    )
            if "username" in values:
                db.execute(
                    "UPDATE accounts SET username_key=%s WHERE id=%s",
                    (values["username"].casefold(), account_id),
                )
            if "password" in values:
                salt = secrets.token_bytes(16)
                db.execute(
                    "UPDATE accounts SET salt=%s,password_hash=%s WHERE id=%s",
                    (
                        salt,
                        self.store.password_hash(values["password"], salt),
                        account_id,
                    ),
                )
                db.execute("DELETE FROM tokens WHERE account_id=%s", (account_id,))
            if "kamas" in values:
                db.execute(
                    "UPDATE account_wallets SET kamas=%s WHERE account_id=%s",
                    (values["kamas"], account_id),
                )
            if "is_admin" in values and values["is_admin"] != before["is_admin"]:
                db.execute(
                    "INSERT INTO admin_role_audit(account_id,is_admin,operator,reason) VALUES(%s,%s,%s,%s)",
                    (
                        account_id,
                        values["is_admin"],
                        operator,
                        "Admin panel account update",
                    ),
                )
            safe = {k: v for k, v in values.items() if k != "password"}
            if "password" in values:
                safe["password_reset"] = True
            self._audit(db, operator, "account.update", account_id, dict(before), safe)
        return self.account(account_id)

    @staticmethod
    def profiler():
        return admin_profiler.snapshot()

    MAP_SQL = "WITH native AS (SELECT (payload->>'map_id')::integer id FROM native_catalog_records WHERE revision=(SELECT revision FROM native_catalog_active WHERE id=1) AND path='map-inventory.json' AND collection='maps'), ids AS (SELECT id FROM native UNION SELECT map_id FROM characters UNION SELECT map_id FROM admin_map_metadata) SELECT i.id,coalesce(m.name,'') name,coalesce(m.notes,'') notes,EXISTS(SELECT 1 FROM native n WHERE n.id=i.id) installed_geometry,(SELECT count(*) FROM characters c WHERE c.map_id=i.id) character_count,(SELECT count(*) FROM sessions s JOIN characters c ON c.id=s.character_id WHERE c.map_id=i.id AND s.expires_at>now()) online_count FROM ids i LEFT JOIN admin_map_metadata m ON m.map_id=i.id"

    def maps(self, q="", limit=50, offset=0):
        with self.store.connection() as db:
            names = admin_map_catalog.load(db)
            query = str(q)[:100]
            native_ids = [
                int(key)
                for key, name in names.items()
                if query.casefold() in name.casefold()
            ]
            result = self._list(
                db,
                self.MAP_SQL
                + " WHERE i.id::text ILIKE %s OR m.name ILIKE %s OR i.id=ANY(%s) ORDER BY online_count DESC,character_count DESC,i.id",
                ("%" + query + "%", "%" + query + "%", native_ids),
                limit,
                offset,
            )
            result["items"] = [
                admin_map_catalog.label(row, names) for row in result["items"]
            ]
            return result

    def map(self, map_id):
        with self.store.connection() as db:
            row = db.execute(self.MAP_SQL + " WHERE i.id=%s", (map_id,)).fetchone()
            if row is None:
                raise LookupError("Map not found")
            result = dict(row)
            result["characters"] = [
                dict(r)
                for r in db.execute(
                    "SELECT c.id,c.account_id,c.name,c.level,c.instance_id,c.x,c.y,c.z,EXISTS(SELECT 1 FROM sessions s WHERE s.character_id=c.id AND s.expires_at>now()) online FROM characters c WHERE c.map_id=%s ORDER BY c.id LIMIT 100",
                    (map_id,),
                )
            ]
            result = admin_map_catalog.label(result, admin_map_catalog.load(db))
            result.update(admin_map_catalog.details(db, map_id))
            return result

    def update_map(self, map_id, data, operator):
        if not isinstance(data, dict) or not data or set(data) - {"name", "notes"}:
            raise ValueError("Only map display name and operator notes can be edited")
        self.map(map_id)
        supplied = {
            field: self.text(value, field, 200 if field == "name" else 5000, True)
            for field, value in data.items()
        }
        with self.store.connection() as db:
            db.execute("SELECT pg_advisory_xact_lock(%s,%s)", (109, map_id))
            prior = db.execute(
                "SELECT name,notes FROM admin_map_metadata WHERE map_id=%s FOR UPDATE",
                (map_id,),
            ).fetchone()
            name = supplied.get("name", prior["name"] if prior else "")
            notes = supplied.get("notes", prior["notes"] if prior else "")
            db.execute(
                "INSERT INTO admin_map_metadata(map_id,name,notes) VALUES(%s,%s,%s) ON CONFLICT(map_id) DO UPDATE SET name=excluded.name,notes=excluded.notes,updated_at=now()",
                (map_id, name, notes),
            )
            self._audit(
                db,
                operator,
                "map.metadata",
                map_id,
                dict(prior) if prior else None,
                dict(name=name, notes=notes),
            )
        return self.map(map_id)

    def list_catalog(self, kind, q="", limit=50, offset=0):
        table = {"categories": "shop_categories", "articles": "shop_articles"}[kind]
        with self.store.connection() as db:
            return self._list(
                db,
                "SELECT * FROM "
                + table
                + " WHERE name ILIKE %s OR key ILIKE %s ORDER BY id",
                ("%" + str(q)[:100] + "%",) * 2,
                limit,
                offset,
            )

    def save_catalog(self, kind, identity, data, operator):
        fields = {"key", "name", "description", "enabled"} | (
            {"sort_order"}
            if kind == "categories"
            else {"item_ref", "quantity", "price_kamas", "category"}
        )
        if not isinstance(data, dict) or not data or set(data) - fields:
            raise ValueError("Unsupported catalog field")
        values = dict(data)
        for field in ("key", "name", "description", "category"):
            if field in values:
                values[field] = self.text(
                    values[field],
                    field,
                    5000 if field == "description" else 200,
                    field == "description",
                )
        if "key" in values and not re.fullmatch(
            r"[a-z0-9][a-z0-9_-]{0,99}", values["key"]
        ):
            raise ValueError(
                "Key must contain lowercase letters, numbers, underscores or hyphens"
            )
        if "enabled" in values and type(values["enabled"]) is not bool:
            raise ValueError("Invalid enabled flag")
        for field, low, high in [
            ("sort_order", -100000, 100000),
            ("item_ref", 1, 2147483647),
            ("quantity", 1, 32767),
            ("price_kamas", 1, 2147483647),
        ]:
            if field in values:
                self.integer(values[field], low, high, field)
        table = {"categories": "shop_categories", "articles": "shop_articles"}[kind]
        with self.store.connection() as db:
            before = (
                db.execute(
                    "SELECT * FROM " + table + " WHERE id=%s FOR UPDATE", (identity,)
                ).fetchone()
                if identity
                else None
            )
            if identity and before is None:
                raise LookupError("Catalog entry not found")
            merged = dict(before or {}, **values)
            required = {"key", "name"} | (
                {"item_ref", "category", "price_kamas"} if kind == "articles" else set()
            )
            if not required <= set(merged):
                raise ValueError("Missing required catalog fields")
            if kind == "articles":
                rule = db.execute(
                    "SELECT payload FROM native_catalog_records WHERE revision=(SELECT revision FROM native_catalog_active WHERE id=1) AND path='item-stack-rules.json' AND collection='items' AND record_key=%s",
                    (str(merged["item_ref"]),),
                ).fetchone()
                if rule is None or merged.get("quantity", 1) > min(
                    int(rule["payload"]["maximum"]), 32767
                ):
                    raise ValueError(
                        "Item or quantity is unsupported by the native stack catalog"
                    )
            keys = list(values)
            if identity:
                sql = (
                    "UPDATE "
                    + table
                    + " SET "
                    + ",".join(k + "=%s" for k in keys)
                    + " WHERE id=%s RETURNING *"
                )
                row = db.execute(
                    sql, tuple(values[k] for k in keys) + (identity,)
                ).fetchone()
            else:
                sql = (
                    "INSERT INTO "
                    + table
                    + "("
                    + ",".join(keys)
                    + ") VALUES("
                    + ",".join(["%s"] * len(keys))
                    + ") RETURNING *"
                )
                row = db.execute(sql, tuple(values[k] for k in keys)).fetchone()
            self._audit(
                db,
                operator,
                kind + (".update" if identity else ".create"),
                row["id"],
                dict(before) if before else None,
                dict(row),
            )
            return dict(row)

    def items(self, q="", limit=50, offset=0):
        query = str(q)[:100]
        with self.store.connection() as db:
            result = self._list(
                db,
                "SELECT payload FROM native_catalog_records WHERE revision=(SELECT revision FROM native_catalog_active WHERE id=1) AND path='item-stack-rules.json' AND collection='items' AND (payload->>'reference')::integer>0 AND (payload->>'name' ILIKE %s OR record_key=%s) ORDER BY record_key",
                ("%" + query + "%", query),
                limit,
                offset,
            )
            result["items"] = [r["payload"] for r in result["items"]]
            return result

    def orders(self, q="", limit=50, offset=0):
        with self.store.connection() as db:
            return self._list(
                db,
                "SELECT o.*,a.username FROM shop_orders o JOIN accounts a ON a.id=o.account_id WHERE a.username ILIKE %s ORDER BY o.created_at DESC",
                ("%" + str(q)[:100] + "%",),
                limit,
                offset,
            )

    def audit(self, q="", limit=50, offset=0):
        with self.store.connection() as db:
            return self._list(
                db,
                "SELECT * FROM admin_panel_audit ORDER BY id DESC",
                (),
                limit,
                offset,
            )
