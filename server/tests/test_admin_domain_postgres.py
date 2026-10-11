"""Isolated PostgreSQL contracts for the operator panel domain.

These cases create a UUID schema through PostgresCase and never target runtime
tables. Opt in explicitly because they run all migrations and write fixture rows.
"""
import os
import hashlib
from unittest.mock import patch

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase


class AdminDomainPostgresTests(PostgresCase):
    def setUp(self):
        if os.environ.get("WAKFU_RUN_ADMIN_POSTGRES_TESTS") != "1":
            self.skipTest(
                "Set WAKFU_RUN_ADMIN_POSTGRES_TESTS=1 for isolated admin DB tests"
            )
        super().setUp()
        from wakfu_server.admin_domain import AdminService

        self.admin = AdminService(self.store)
        self.operator = "admin-panel-test"

    def _create_character(self, account_id, name):
        with self.store.connection() as db:
            return db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
                "VALUES(%s,%s,%s,1,false,0,0,'[]','{}',100,100) RETURNING id",
                (account_id, name, name.casefold()),
            ).fetchone()["id"]

    def _live_character(self, account_id, name):
        character_id = self._create_character(account_id, name)
        generation = self.store.begin_session(account_id)
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET character_id=%s WHERE account_id=%s",
                (character_id, account_id),
            )
        return character_id, generation

    def _publish_native_records(self, map_id=None, item_ref=None):
        """Publish the minimal native records consumed by admin catalog queries."""
        revision = ("a" if map_id is not None else "b") * 64
        records = []
        if item_ref is not None:
            records.append(
                (
                    "item-stack-rules.json",
                    "items",
                    str(item_ref),
                    {
                        "reference": item_ref,
                        "name": "Fixture native item",
                        "maximum": 10,
                    },
                )
            )
        if map_id is not None:
            records.extend(
                (
                    (
                        "map-inventory.json",
                        "maps",
                        str(map_id),
                        {"id": map_id, "map_id": str(map_id)},
                    ),
                    (
                        "native-map-objects.json",
                        "$",
                        "fixture-object",
                        {"map_id": str(map_id)},
                    ),
                )
            )
        paths = sorted({entry[0] for entry in records})
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_catalog_releases(revision,document_count,source_bytes,complete,completed_at) "
                "VALUES(%s,%s,%s,true,now())",
                (revision, len(paths), 2 * len(paths)),
            )
            for path in paths:
                raw = b"{}"
                db.execute(
                    "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        revision,
                        path,
                        raw,
                        hashlib.sha256(raw).hexdigest(),
                        len(raw),
                        sum(1 for entry in records if entry[0] == path),
                    ),
                )
            for path, collection, key, payload in records:
                db.execute(
                    "INSERT INTO native_catalog_records(revision,path,collection,record_key,payload) "
                    "VALUES(%s,%s,%s,%s,%s)",
                    (revision, path, collection, key, Jsonb(payload)),
                )
            db.execute(
                "INSERT INTO native_catalog_active(id,revision) VALUES(1,%s)",
                (revision,),
            )

    def test_account_create_update_is_audited_and_never_records_password(self):
        created = self.admin.create_account(
            {
                "username": "adminfixture",
                "password": "fixture-password-1",
                "kamas": 250,
            },
            self.operator,
        )
        self.assertFalse(created["is_admin"])
        self.assertEqual(250, created["kamas"])
        self.assertNotIn("password", created)

        updated = self.admin.update_account(
            created["id"],
            {
                "username": "adminfixture2",
                "password": "replacement-password-2",
                "kamas": 800,
            },
            self.operator,
        )
        self.assertEqual("adminfixture2", updated["username"])
        self.assertEqual(800, updated["kamas"])
        self.assertNotIn("password", updated)
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT action,before_data,after_data FROM admin_panel_audit "
                "WHERE operator=%s ORDER BY id",
                (self.operator,),
            ).fetchall()
        self.assertEqual(
            ["account.create", "account.update"], [r["action"] for r in rows]
        )
        self.assertNotIn("fixture-password-1", repr(rows))
        self.assertNotIn("replacement-password-2", repr(rows))
        self.assertTrue(rows[1]["after_data"]["password_reset"])

    def test_account_validation_rejects_role_coercion_and_duplicate_username(self):
        first = self.admin.create_account(
            {"username": "adminvalid", "password": "fixture-password-1"},
            self.operator,
        )
        with self.assertRaisesRegex(ValueError, "administrator flag"):
            self.admin.update_account(first["id"], {"is_admin": 1}, self.operator)
        with self.assertRaises(UniqueViolation):
            self.admin.create_account(
                {"username": "adminvalid", "password": "fixture-password-2"},
                self.operator,
            )

    def test_account_with_live_session_cannot_be_edited(self):
        created = self.admin.create_account(
            {"username": "adminonline", "password": "fixture-password-1"},
            self.operator,
        )
        generation = self.store.begin_session(created["id"])
        with self.assertRaisesRegex(ValueError, "active session"):
            self.admin.update_account(created["id"], {"kamas": 900}, self.operator)
        self.store.end_session(created["id"], generation)

    def test_shop_category_crud_and_field_allowlist_are_audited(self):
        category = self.admin.save_catalog(
            "categories",
            None,
            {
                "key": "panel-fixture",
                "name": "Panel fixture",
                "description": "temporary",
                "sort_order": 900,
                "enabled": True,
            },
            self.operator,
        )
        changed = self.admin.save_catalog(
            "categories",
            category["id"],
            {"name": "Panel updated", "enabled": False},
            self.operator,
        )
        self.assertEqual("Panel updated", changed["name"])
        self.assertFalse(changed["enabled"])
        with self.assertRaisesRegex(ValueError, "Unsupported catalog field"):
            self.admin.save_catalog(
                "categories",
                category["id"],
                {"sql": "DROP TABLE accounts"},
                self.operator,
            )
        with self.store.connection() as db:
            actions = db.execute(
                "SELECT action FROM admin_panel_audit WHERE operator=%s ORDER BY id",
                (self.operator,),
            ).fetchall()
        self.assertEqual(
            ["categories.create", "categories.update"], [r["action"] for r in actions]
        )

    def test_article_create_uses_active_native_item_and_stack_limit(self):
        self._publish_native_records(item_ref=987654)
        article = self.admin.save_catalog(
            "articles",
            None,
            {
                "key": "panel-native-item",
                "name": "Native fixture",
                "item_ref": 987654,
                "quantity": 10,
                "price_kamas": 125,
                "category": "items",
                "enabled": True,
            },
            self.operator,
        )
        self.assertEqual(987654, article["item_ref"])
        self.assertEqual(10, article["quantity"])
        with self.assertRaisesRegex(ValueError, "Item or quantity"):
            self.admin.save_catalog(
                "articles",
                None,
                {
                    "key": "panel-invalid-item",
                    "name": "Invalid fixture",
                    "item_ref": 987654,
                    "quantity": 11,
                    "price_kamas": 125,
                    "category": "items",
                },
                self.operator,
            )
        self.assertEqual(
            "panel-native-item",
            self.admin.list_catalog("articles", "panel-native-item")["items"][0]["key"],
        )

    def test_dashboard_and_map_lists_include_active_and_fixture_state(self):
        map_id = 987653
        self._publish_native_records(map_id=map_id)
        account = self.store.register("dashboardfixture", "fixture-password-1")["id"]
        with self.store.connection() as db:
            character_id = db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp,map_id,x,y) "
                "VALUES(%s,'Dashboard Fixture','dashboard fixture',1,false,0,0,'[]','{}',100,100,%s,4,5) RETURNING id",
                (account, map_id),
            ).fetchone()["id"]
        generation = self.store.begin_session(account)
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET character_id=%s WHERE account_id=%s",
                (character_id, account),
            )
        self.addCleanup(lambda: self.store.end_session(account, generation))

        dashboard = self.admin.dashboard()
        self.assertEqual(1, dashboard["counts"]["online"])
        self.assertEqual("dashboardfixture", dashboard["online"][0]["username"])
        listed = self.admin.maps(str(map_id))
        self.assertEqual(map_id, listed["items"][0]["id"])
        detail = self.admin.map(map_id)
        self.assertEqual(1, detail["native_objects_count"])
        self.assertEqual("Dashboard Fixture", detail["characters"][0]["name"])

    def test_map_notes_round_trip_is_audited_and_does_not_change_world_position(self):
        account = self.store.register("mapfixture", "fixture-password-1")["id"]
        with self.store.connection() as db:
            map_id = 987654
            character_id = db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp,map_id,x,y) "
                "VALUES(%s,'Map Fixture','map fixture',1,false,0,0,'[]','{}',100,100,%s,12,-4) RETURNING id",
                (account, map_id),
            ).fetchone()["id"]
        result = self.admin.update_map(
            map_id, {"name": "Fixture map", "notes": "operator note"}, self.operator
        )
        self.assertEqual("Fixture map", result["name"])
        self.assertEqual("operator note", result["notes"])
        partial = self.admin.update_map(
            map_id, {"notes": "revised operator note"}, self.operator
        )
        self.assertEqual("Fixture map", partial["name"])
        self.assertEqual("revised operator note", partial["notes"])
        with self.store.connection() as db:
            actor = db.execute(
                "SELECT map_id,x,y FROM characters WHERE id=%s", (character_id,)
            ).fetchone()
            audit = db.execute(
                "SELECT action,target,after_data FROM admin_panel_audit WHERE operator=%s ORDER BY id DESC LIMIT 1",
                (self.operator,),
            ).fetchone()
        self.assertEqual((map_id, 12, -4), (actor["map_id"], actor["x"], actor["y"]))
        self.assertEqual("map.metadata", audit["action"])
        self.assertEqual(str(map_id), audit["target"])
        self.assertEqual("revised operator note", audit["after_data"]["notes"])

    def test_item_grant_uses_native_stack_limit_and_records_pending_receipt(self):
        self._publish_native_records(item_ref=987650)
        account = self.store.register("grantfixture", "fixture-password-1")["id"]
        character = self._create_character(account, "Grant Fixture")
        with patch.object(
            self.admin,
            "_world",
            side_effect=[
                [{"character_id": character, "generation": "live-generation"}],
                {"handle": "grant-handle", "status": "pending"},
            ],
        ) as world:
            result = self.admin.grant_item(
                character,
                {"item_ref": 987650, "quantity": 2, "request_id": "grant-fixture-1"},
                self.operator,
            )
        self.assertEqual("pending", result["status"])
        self.assertEqual("grant-handle", result["handle"])
        self.assertEqual(2, world.call_count)
        with self.store.connection() as db:
            audit = db.execute(
                "SELECT action,after_data FROM admin_panel_audit WHERE operator=%s ORDER BY id DESC LIMIT 1",
                (self.operator,),
            ).fetchone()
        self.assertEqual("character.item_delivery", audit["action"])
        self.assertEqual("pending", audit["after_data"]["status"])

    def test_item_grant_rejects_offline_and_overstack_before_reporting_success(self):
        self._publish_native_records(item_ref=987651)
        account = self.store.register("offlinefixture", "fixture-password-1")["id"]
        character = self._create_character(account, "Offline Fixture")
        payload = {"item_ref": 987651, "quantity": 2, "request_id": "grant-offline-1"}
        with patch.object(self.admin, "_world", return_value=[]) as world:
            with self.assertRaisesRegex(ValueError, "offline"):
                self.admin.grant_item(character, payload, self.operator)
        self.assertEqual(1, world.call_count)
        with patch.object(self.admin, "_world") as world:
            with self.assertRaisesRegex(ValueError, "Item or quantity"):
                self.admin.grant_item(
                    character,
                    {**payload, "quantity": 11, "request_id": "grant-overstack-1"},
                    self.operator,
                )
        world.assert_not_called()
        with self.store.connection() as db:
            count = db.execute(
                "SELECT count(*) n FROM admin_panel_audit WHERE operator=%s AND action='character.item_delivery'",
                (self.operator,),
            ).fetchone()["n"]
        self.assertEqual(0, count)

    def test_admin_failure_receipts_keep_failed_status_and_never_translate_to_success(
        self,
    ):
        receipt = self.admin._action_receipt(
            {
                "handle": "failed-handle",
                "status": "failed",
                "error": "El inventario está lleno",
            }
        )
        self.assertEqual("failed", receipt["status"])
        self.assertEqual("Inventory is full; free a slot and retry", receipt["error"])
        self.assertNotIn("result", receipt)

    def test_native_map_labels_are_searchable_and_operator_labels_take_precedence(self):
        self._publish_native_records(map_id=235)
        listed = self.admin.maps("Sufokia")
        self.assertEqual(235, listed["items"][0]["id"])
        self.assertEqual("Sufokia", listed["items"][0]["name"])
        self.assertEqual("native", listed["items"][0]["name_source"])
        updated = self.admin.update_map(235, {"name": "QA harbor"}, self.operator)
        self.assertEqual("QA harbor", updated["name"])
        self.assertEqual("operator", updated["name_source"])

    def test_profiler_unavailable_returns_a_graceful_panel_contract(self):
        with patch.dict(
            "os.environ",
            {
                "WAKFU_ADMIN_PROFILER_REPORT": "/tmp/wakemu-admin-profiler-report-missing.json"
            },
        ), patch("wakfu_server.admin_profiler.urlopen", side_effect=OSError("offline")):
            result = self.admin.profiler()
        self.assertFalse(result["available"])
        self.assertIsNone(result["status"])
        self.assertIsNone(result["report"])
        self.assertIn("unavailable", result["error"].lower())

    def test_character_listing_uses_only_current_generation_redis_movement(self):
        import json
        from unittest.mock import patch

        account = self.store.register("positionfixture", "fixture-password-1")["id"]
        character, generation = self._live_character(account, "Position Fixture")
        with self.store.connection() as db:
            baseline_row = db.execute(
                "SELECT map_id,instance_id,x,y,z,direction FROM characters WHERE id=%s",
                (character,),
            ).fetchone()
        baseline = dict(baseline_row)
        current = {**baseline, "x": baseline["x"] + 2, "y": baseline["y"] + 3}
        record = json.dumps(
            {
                "version": 2,
                "owner": [account, generation, character],
                "baseline": baseline,
                "current": current,
            }
        ).encode()

        class Pipeline:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def hget(self, *_args):
                return self

            def execute(self):
                return [record]

        class Client:
            def pipeline(self, **_kwargs):
                return Pipeline()

            def close(self):
                pass

        with patch.dict(
            "os.environ", {"WAKFU_REDIS_URL": "redis://isolated-test"}
        ), patch("redis.Redis.from_url", return_value=Client()):
            row = self.admin.characters(str(character))["items"][0]
        self.assertEqual((current["x"], current["y"]), (row["x"], row["y"]))
        self.assertEqual("Redis movement journal", row["position_source"])

        # A newer generation must not inherit the old owner's movement record.
        self.store.end_session(account, generation)
        next_generation = self.store.begin_session(account)
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET character_id=%s WHERE account_id=%s",
                (character, account),
            )
        with patch.dict(
            "os.environ", {"WAKFU_REDIS_URL": "redis://isolated-test"}
        ), patch("redis.Redis.from_url", return_value=Client()):
            stale = self.admin.characters(str(character))["items"][0]
        self.assertEqual("PostgreSQL", stale["position_source"])
        self.assertEqual(baseline["x"], stale["x"])
        self.store.end_session(account, next_generation)
