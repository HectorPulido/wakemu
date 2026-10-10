from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
from pathlib import Path
import shutil
import tempfile
from threading import Barrier
import unittest
import uuid

from psycopg.errors import ForeignKeyViolation
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase, isolated_test_url
from wakfu_server.resource_collect import (
    cancel,
    prepare,
    reserve,
    validate_actor_position,
)
from wakfu_server.profession_store import ensure_learned
from wakfu_server.planting_runtime import Plantings
from wakfu_server.combat_groups import Groups
from wakfu_server.wire import proto_field


def harvest_request(action_id, x, y):
    def unsigned(value):
        return value if value >= 0 else value + (1 << 64)

    return (
        proto_field(8, action_id)
        + proto_field(16, unsigned(x))
        + proto_field(24, unsigned(y))
    )


class ResourceOccupationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.clock = [1000.0]
        self.store.clock = lambda: self.clock[0]
        self.account, self.character, self.generation = self.make_actor(
            "occupation-owner", "Occupation Owner"
        )
        self.resource = self.plant(7001, x=self.character["x"], y=self.character["y"])

    def make_actor(self, username, name):
        account = self.store.register(username, "local-password")["id"]
        character = self.store.create_character(account, name)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        ensure_learned(self.store, account, generation, character["id"], [72])
        return account, character, generation

    def plant(self, uid, *, x, y, stage=3):
        resource = dict(
            resource_uid=uid,
            map_id=self.character["map_id"] if hasattr(self, "character") else 1134,
            instance_id=0,
            x=x,
            y=y,
            z=0,
            resource_reference=60,
            stage=stage,
            creation_time=100,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource.values()),
            )
        return resource

    def prepared(self, *, account=None, character=None, generation=None, resource=None):
        account = self.account if account is None else account
        character = self.character if character is None else character
        generation = self.generation if generation is None else generation
        resource = self.resource if resource is None else resource
        return prepare(
            self.store,
            account,
            generation,
            character["id"],
            harvest_request(100, resource["x"], resource["y"]),
            reachable=lambda _character, _resource: True,
        )

    def reserve_prepared(self, prepared=None, **identity):
        return reserve(
            self.store,
            identity.get("account_id", self.account),
            identity.get("generation", self.generation),
            self.prepared() if prepared is None else prepared,
        )

    def row(self, uid):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM resource_harvest_occupations WHERE resource_uid=%s",
                (uid,),
            ).fetchone()

    def test_one_actor_and_one_resource_each_allow_only_one_ticket(self):
        second_resource = self.plant(
            7002, x=self.character["x"] + 1, y=self.character["y"]
        )
        prepared_first = self.prepared(resource=self.resource)
        prepared_second = self.prepared(resource=second_resource)
        first_ticket = self.reserve_prepared(prepared_first)
        with self.assertRaisesRegex(ValueError, "busy"):
            self.reserve_prepared(prepared_second)

        second_account, second_character, second_generation = self.make_actor(
            "occupation-other", "Occupation Other"
        )
        other_prepared = self.prepared(
            account=second_account,
            character=second_character,
            generation=second_generation,
            resource=self.resource,
        )
        with self.assertRaisesRegex(ValueError, "busy"):
            self.reserve_prepared(
                other_prepared,
                account_id=second_account,
                generation=second_generation,
            )
        self.assertEqual(
            self.row(self.resource["resource_uid"])["token"], first_ticket["token"]
        )

    def test_reservation_persists_all_five_authoritative_actor_position_fields(self):
        resource = self.plant(
            7003, x=self.character["x"] + 3, y=self.character["y"] + 4
        )
        prepared = self.prepared(resource=resource)
        ticket = self.reserve_prepared(prepared)
        row = self.row(resource["resource_uid"])
        with self.store.connection() as db:
            actual = db.execute(
                "SELECT map_id,instance_id,x,y,z FROM characters WHERE id=%s",
                (self.character["id"],),
            ).fetchone()
        self.assertEqual(
            tuple(
                row[key]
                for key in (
                    "actor_map_id",
                    "actor_instance_id",
                    "actor_x",
                    "actor_y",
                    "actor_z",
                )
            ),
            tuple(actual[key] for key in ("map_id", "instance_id", "x", "y", "z")),
        )
        self.assertEqual(row["actor_x"], self.character["x"])
        self.assertNotEqual(row["actor_x"], row["resource_snapshot"]["x"])
        self.assertEqual(row["resource_uid"], ticket["resource_uid"])

    def test_actor_position_validator_accepts_snapshot_and_rejects_each_changed_field(
        self,
    ):
        character = {
            "map_id": 1134,
            "instance_id": 77,
            "x": -12,
            "y": -8,
            "z": -1,
        }
        occupation = {
            "actor_map_id": 1134,
            "actor_instance_id": 77,
            "actor_x": -12,
            "actor_y": -8,
            "actor_z": -1,
        }
        self.assertIsNone(validate_actor_position(character, occupation))
        for key in ("map_id", "instance_id", "x", "y", "z"):
            moved = dict(character, **{key: character[key] + 1})
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "moved"):
                validate_actor_position(moved, occupation)

    def test_migration_drops_in_flight_reservations_missing_actor_snapshot(self):
        from wakfu_server.postgres import Database, migrate
        from wakfu_server.storage.store import Store

        base_url = isolated_test_url()
        password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        migrations = Path(os.environ["WAKFU_MIGRATIONS_TEST_DIR"])
        admin = Database(base_url, password_file=password_file)
        schema = "harvest_snapshot_migration_" + uuid.uuid4().hex
        try:
            with admin.connection() as db:
                db.execute(f"CREATE SCHEMA {schema}")
            scoped_url = make_conninfo(base_url, options=f"-c search_path={schema}")
            store = Store(scoped_url, password_file=password_file)
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    prefix_dir = Path(temp_dir)
                    for migration in sorted(migrations.glob("*.sql")):
                        if int(migration.name[:3]) <= 13:
                            shutil.copyfile(migration, prefix_dir / migration.name)
                    with store.connection() as db:
                        migrate(db, prefix_dir)
                    account = store.register("old-harvest", "local-password")["id"]
                    # This migration probe intentionally stops at schema 013,
                    # before deleted_at was introduced in migration 046. Do not
                    # use the current Store.create_character() against this old
                    # schema: insert the minimal legacy row the test needs.
                    with store.connection() as db:
                        character = db.execute(
                            "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,"
                            "colors,appearance,hp,max_hp) VALUES(%s,%s,%s,1,false,0,0,'[]','{}',100,100) "
                            "RETURNING id,map_id,instance_id,x,y,z",
                            (account, "Old Harvest", "old harvest"),
                        ).fetchone()
                    resource = dict(
                        resource_uid=89001,
                        map_id=character["map_id"],
                        instance_id=character["instance_id"],
                        x=character["x"],
                        y=character["y"],
                        z=0,
                        resource_reference=60,
                        stage=3,
                        creation_time=1,
                    )
                    now = store.now()
                    with store.connection() as db:
                        db.execute(
                            "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                            "resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            tuple(resource.values()),
                        )
                        db.execute(
                            "INSERT INTO resource_harvest_occupations("
                            "resource_uid,token,account_id,generation,character_id,action_id,"
                            "started_at,completes_at,expires_at,resource_snapshot) "
                            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                89001,
                                "pre-014-ticket",
                                account,
                                "old-generation",
                                character["id"],
                                100,
                                now,
                                now + timedelta(seconds=3),
                                now + timedelta(seconds=8),
                                Jsonb(resource),
                            ),
                        )
                    with store.connection() as db:
                        self.assertEqual(
                            db.execute(
                                "SELECT count(*) FROM resource_harvest_occupations"
                            ).fetchone()["count"],
                            1,
                        )
                        migrate(db, migrations)
                        self.assertEqual(
                            db.execute(
                                "SELECT count(*) FROM resource_harvest_occupations"
                            ).fetchone()["count"],
                            0,
                        )
                        columns = {
                            row["column_name"]
                            for row in db.execute(
                                "SELECT column_name FROM information_schema.columns "
                                "WHERE table_schema=%s AND table_name='resource_harvest_occupations'",
                                (schema,),
                            )
                        }
                    self.assertTrue(
                        {
                            "actor_map_id",
                            "actor_instance_id",
                            "actor_x",
                            "actor_y",
                            "actor_z",
                        }.issubset(columns)
                    )
            finally:
                store.close()
        finally:
            with admin.connection() as db:
                db.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            admin.close()

    def test_stale_generation_and_foreign_character_cannot_reserve(self):
        prepared = self.prepared()
        stale_generation = self.generation
        new_generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, new_generation, self.character["id"])
        with self.assertRaises(ValueError):
            reserve(self.store, self.account, stale_generation, prepared)

        other_account, _, other_generation = self.make_actor(
            "occupation-foreign", "Occupation Foreign"
        )
        with self.assertRaises(ValueError):
            reserve(self.store, other_account, other_generation, prepared)
        self.assertIsNone(self.row(self.resource["resource_uid"]))

    def test_moved_actor_changed_resource_tampered_action_and_removed_profession_fail(
        self,
    ):
        prepared = self.prepared()
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=x+1 WHERE id=%s", (self.character["id"],)
            )
        with self.assertRaisesRegex(ValueError, "moved"):
            reserve(self.store, self.account, self.generation, prepared)
        self.assertIsNone(self.row(self.resource["resource_uid"]))

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=x-1 WHERE id=%s", (self.character["id"],)
            )
            db.execute(
                "UPDATE planted_resources SET stage=2 WHERE resource_uid=%s",
                (self.resource["resource_uid"],),
            )
        with self.assertRaisesRegex(ValueError, "changed"):
            reserve(self.store, self.account, self.generation, prepared)
        with self.store.connection() as db:
            db.execute(
                "UPDATE planted_resources SET stage=3 WHERE resource_uid=%s",
                (self.resource["resource_uid"],),
            )

        tampered = self.prepared()
        tampered["request"]["action_id"] = 203
        with self.assertRaisesRegex(ValueError, "action changed"):
            reserve(self.store, self.account, self.generation, tampered)

        prepared = self.prepared()
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM account_professions WHERE account_id=%s AND profession_id=72",
                (self.account,),
            )
        with self.assertRaisesRegex(ValueError, "unlearned"):
            reserve(self.store, self.account, self.generation, prepared)
        self.assertIsNone(self.row(self.resource["resource_uid"]))

    def test_expiry_allows_takeover_and_old_cancel_cannot_remove_new_ticket(self):
        prepared = self.prepared()
        old = self.reserve_prepared(prepared)
        self.clock[0] = old["expires_at"].timestamp()
        replacement = self.reserve_prepared(prepared)
        self.assertNotEqual(old["token"], replacement["token"])
        self.assertFalse(cancel(self.store, old))
        self.assertEqual(
            self.row(self.resource["resource_uid"])["token"], replacement["token"]
        )
        self.assertTrue(cancel(self.store, replacement))
        self.assertFalse(cancel(self.store, replacement))

    def test_ticket_survives_store_reopen_and_reserve_does_not_grant(self):
        before_items = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ]
        before_resource = self.resource.copy()
        ticket = self.reserve_prepared()
        reopened = self.reopen()
        with reopened.connection() as db:
            row = db.execute(
                "SELECT * FROM resource_harvest_occupations WHERE resource_uid=%s",
                (self.resource["resource_uid"],),
            ).fetchone()
            self.assertEqual(row["token"], ticket["token"])
            self.assertEqual(
                (row["completes_at"] - row["started_at"]).total_seconds(), 3
            )
            self.assertEqual(
                (row["expires_at"] - row["completes_at"]).total_seconds(), 5
            )
            self.assertEqual(
                db.execute("SELECT count(*) FROM planting_receipts").fetchone()[
                    "count"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM resource_harvest_occupations"
                ).fetchone()["count"],
                1,
            )
        self.assertTrue(cancel(reopened, ticket))
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"],
            before_items,
        )
        with self.store.connection() as db:
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM planted_resources WHERE resource_uid=%s",
                        (self.resource["resource_uid"],),
                    ).fetchone()
                ),
                before_resource,
            )

    def test_malformed_boolean_grace_policy_fails_closed(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='resource_harvest_occupation'",
                (Jsonb({"completion_grace_ms": True}),),
            )
        with self.assertRaisesRegex(ValueError, "policy"):
            self.reserve_prepared()
        self.assertIsNone(self.row(self.resource["resource_uid"]))

    def test_malformed_boolean_native_duration_fails_closed(self):
        prepared = self.prepared()
        prepared["rule"]["duration_ms"] = True
        with self.assertRaisesRegex(ValueError, "action changed"):
            self.reserve_prepared(prepared)
        self.assertIsNone(self.row(self.resource["resource_uid"]))

    def test_database_forbids_account_character_mismatch(self):
        other_account, _, _ = self.make_actor(
            "occupation-fk-owner", "Occupation Foreign Key"
        )
        now = self.store.now()
        with self.assertRaises(ForeignKeyViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO resource_harvest_occupations("
                    "resource_uid,token,account_id,generation,character_id,action_id,"
                    "started_at,completes_at,expires_at,resource_snapshot,"
                    "actor_map_id,actor_instance_id,actor_x,actor_y,actor_z) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        self.resource["resource_uid"],
                        "mismatched-account-character",
                        other_account,
                        "generation",
                        self.character["id"],
                        100,
                        now,
                        now + timedelta(milliseconds=1),
                        now + timedelta(milliseconds=2),
                        Jsonb(self.resource),
                        self.character["map_id"],
                        self.character["instance_id"],
                        self.character["x"],
                        self.character["y"],
                        self.character["z"],
                    ),
                )

    def test_growth_waits_for_live_occupation_and_proceeds_after_cancel_or_expiry(self):
        runtime = Plantings(self.store)
        groups = Groups()
        # This unrelated stage-3 flora must be younger than its new local
        # graph delay; the test only advances the two stage-1 targets below.
        with self.store.connection() as db:
            db.execute(
                "UPDATE planted_resources SET creation_time=%s WHERE resource_uid=%s",
                (int(self.clock[0] * 1000), self.resource["resource_uid"]),
            )
        live = self.plant(
            7010, x=self.character["x"] + 1, y=self.character["y"], stage=1
        )
        live["creation_time"] = int(self.clock[0] * 1000) - 30000
        with self.store.connection() as db:
            db.execute(
                "UPDATE planted_resources SET creation_time=%s WHERE resource_uid=%s",
                (live["creation_time"], live["resource_uid"]),
            )
        live_prepared = prepare(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            harvest_request(329, live["x"], live["y"]),
            reachable=lambda _character, _resource: True,
        )
        live_ticket = reserve(self.store, self.account, self.generation, live_prepared)
        self.assertEqual(runtime.mature(groups, publish=lambda _delivery: None), [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT stage FROM planted_resources WHERE resource_uid=%s",
                    (live["resource_uid"],),
                ).fetchone()["stage"],
                1,
            )
        self.assertTrue(cancel(self.store, live_ticket))
        grown = runtime.mature(groups, publish=lambda _delivery: None)
        self.assertEqual(len(grown), 1)
        self.assertEqual(grown[0]["resource_uid"], live["resource_uid"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT stage FROM planted_resources WHERE resource_uid=%s",
                    (live["resource_uid"],),
                ).fetchone()["stage"],
                2,
            )

        expired = self.plant(
            7011,
            x=self.character["x"] + 2,
            y=self.character["y"],
            stage=1,
        )
        expired_prepared = prepare(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            harvest_request(329, expired["x"], expired["y"]),
            reachable=lambda _character, _resource: True,
        )
        expired_ticket = reserve(
            self.store, self.account, self.generation, expired_prepared
        )
        self.clock[0] = expired_ticket["expires_at"].timestamp()
        grown = runtime.mature(groups, publish=lambda _delivery: None)
        self.assertEqual(len(grown), 1)
        self.assertEqual(grown[0]["resource_uid"], expired["resource_uid"])
        self.assertTrue(cancel(self.store, expired_ticket))
        self.assertFalse(cancel(self.store, expired_ticket))

    def test_concurrent_actors_racing_for_same_resource_have_one_winner(self):
        second_account, second_character, second_generation = self.make_actor(
            "occupation-racer", "Occupation Racer"
        )
        first = self.prepared()
        second = self.prepared(
            account=second_account,
            character=second_character,
            generation=second_generation,
        )
        barrier = Barrier(2)

        def compete(account, generation, prepared):
            barrier.wait()
            try:
                return reserve(self.store, account, generation, prepared)
            except ValueError as error:
                if "busy" in str(error):
                    return "busy"
                raise

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda args: compete(*args),
                    (
                        (self.account, self.generation, first),
                        (second_account, second_generation, second),
                    ),
                )
            )
        self.assertEqual(sum(result != "busy" for result in results), 1)
        self.assertEqual(sum(result == "busy" for result in results), 1)
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
