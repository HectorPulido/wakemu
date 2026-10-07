import struct
import unittest
from psycopg.errors import CheckViolation, GeneratedAlways, UniqueViolation
from psycopg.types.json import Jsonb
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.planting import prepare, complete, publish_groups, SEEDS, RESOURCES
from wakfu_server.profession_store import ensure_learned
from wakfu_server.profession_wire import MAX_XP
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_groups import Groups
from wakfu_server.ecology_feedback import information


class PlantingTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("planting", "password")["id"]
        self.char = self.store.create_character(self.account, "Planting Player")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])

    def seed(self, ref, *, quantity=3):
        item = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=ref,
            quantity=quantity,
            container=self.char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=SEEDS,
        )
        ensure_learned(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            [SEEDS[ref]["profession_id"]],
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=%s WHERE account_id=%s AND profession_id=%s",
                (MAX_XP, self.account, SEEDS[ref]["profession_id"]),
            )
        body = struct.pack(">iqii", SEEDS[ref]["action_id"], item["uid"], 10, 11)
        prepared = prepare(
            self.store,
            self.account,
            self.generation,
            self.char,
            body,
            authorize_cell=lambda *args: 0,
        )
        return item, body, prepared

    def test_failed_plant_consumes_one_seed_and_records_no_world_or_xp_effect(self):
        item, _, prepared = self.seed(4275)
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=321 WHERE account_id=%s AND profession_id=%s",
                (self.account, SEEDS[4275]["profession_id"]),
            )
        result = complete(
            self.store,
            self.account,
            self.generation,
            prepared,
            operation_id="failed-herb-1",
            stage=1,
            creation_time=123,
            result_prefix=(0, 1),
            success=False,
        )
        self.assertFalse(result["success"])
        self.assertIsNone(result["resource"])
        self.assertIsNone(result["group"])
        self.assertEqual(
            [packet[0] for packet in result["packets"]], [12954, 12470, 349]
        )
        self.assertEqual(result["packets"][0][1][-1], 0)
        self.assertEqual(
            result["packets"][1], (12470, struct.pack(">qh", item["uid"], -1))
        )
        inventory = self.store.character(self.account, self.char["id"])[
            "inventory_items"
        ]
        self.assertEqual(inventory[0]["quantity"], 2)
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT success,resource,group_payload FROM planting_receipts WHERE operation_id=%s",
                ("failed-herb-1",),
            ).fetchone()
            self.assertFalse(receipt["success"])
            self.assertIsNone(receipt["resource"])
            self.assertIsNone(receipt["group_payload"])
            self.assertEqual(
                db.execute("SELECT count(*) FROM planted_resources").fetchone()[
                    "count"
                ],
                0,
            )
            self.assertEqual(
                db.execute("SELECT count(*) FROM planting_growth_outbox").fetchone()[
                    "count"
                ],
                0,
            )
            profession = db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=%s",
                (self.account, SEEDS[4275]["profession_id"]),
            ).fetchone()
            self.assertEqual(profession["xp"], 321)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM profession_xp_receipts WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["count"],
                0,
            )

    def test_failed_plant_consumes_last_seed_and_duplicate_outcome_is_stable(self):
        item, _, prepared = self.seed(4275, quantity=1)
        kwargs = dict(
            operation_id="failed-last-seed",
            stage=1,
            creation_time=123,
            result_prefix=(0, 1),
            success=False,
        )
        first = complete(self.store, self.account, self.generation, prepared, **kwargs)
        self.assertFalse(first["success"])
        self.assertEqual(first["character"]["inventory_items"], [])
        replay = complete(
            self.store,
            self.account,
            self.generation,
            prepared,
            **{**kwargs, "success": True},
        )
        self.assertTrue(replay["duplicate"])
        self.assertFalse(replay["success"])
        self.assertIsNone(replay["resource"])
        self.assertEqual(replay["packets"], [])
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"],
            [],
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM planted_resources").fetchone()[
                    "count"
                ],
                0,
            )
            self.assertEqual(
                db.execute("SELECT count(*) FROM planting_receipts").fetchone()[
                    "count"
                ],
                1,
            )

    def test_failure_outcome_validation_and_foreign_operation_reuse_roll_back(self):
        item, _, prepared = self.seed(4275)
        args = dict(
            operation_id="failure-operation-owner",
            stage=1,
            creation_time=123,
            result_prefix=(0, 1),
            success=False,
        )
        with self.assertRaises(ValueError):
            complete(
                self.store,
                self.account,
                self.generation,
                prepared,
                **{**args, "success": 1},
            )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            3,
        )
        complete(self.store, self.account, self.generation, prepared, **args)

        foreign_account = self.store.register("planting-foreign", "password")["id"]
        foreign_char = self.store.create_character(foreign_account, "Foreign Planter")
        foreign_generation = self.store.begin_session(foreign_account)
        self.store.select_character(
            foreign_account, foreign_generation, foreign_char["id"]
        )
        foreign_item = grant(
            self.store,
            foreign_account,
            foreign_generation,
            foreign_char["id"],
            reference=4275,
            quantity=2,
            container=foreign_char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=SEEDS,
        )
        ensure_learned(
            self.store,
            foreign_account,
            foreign_generation,
            foreign_char["id"],
            [SEEDS[4275]["profession_id"]],
        )
        foreign_prepared = prepare(
            self.store,
            foreign_account,
            foreign_generation,
            foreign_char,
            struct.pack(">iqii", SEEDS[4275]["action_id"], foreign_item["uid"], 10, 11),
            authorize_cell=lambda *cell_args: 0,
        )
        with self.assertRaises(ValueError):
            complete(
                self.store,
                foreign_account,
                foreign_generation,
                foreign_prepared,
                **args,
            )
        self.assertEqual(
            self.store.character(foreign_account, foreign_char["id"])[
                "inventory_items"
            ][0]["quantity"],
            2,
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM planting_receipts").fetchone()[
                    "count"
                ],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM profession_xp_receipts WHERE account_id=%s",
                    (foreign_account,),
                ).fetchone()["count"],
                0,
            )

    def test_failure_receipt_sql_outcome_constraint_rejects_mismatches(self):
        _, _, prepared = self.seed(4275)
        planted = complete(
            self.store,
            self.account,
            self.generation,
            prepared,
            operation_id="failure-check-constraint",
            stage=1,
            creation_time=123,
            result_prefix=(0, 1),
            success=False,
        )
        invalid_updates = [
            (
                "UPDATE planting_receipts SET success=TRUE WHERE operation_id=%s",
                ("failure-check-constraint",),
            ),
            (
                "UPDATE planting_receipts SET resource=%s WHERE operation_id=%s",
                ('{"resource_uid":1}', "failure-check-constraint"),
            ),
            (
                "UPDATE planting_receipts SET group_payload=%s WHERE operation_id=%s",
                ('{"key":[1,0,1]}', "failure-check-constraint"),
            ),
        ]
        with self.store.connection() as db:
            for query, params in invalid_updates:
                with self.assertRaises(CheckViolation):
                    with db.transaction():
                        db.execute(query, params)

    def test_receipt_resource_uid_is_generated_unique_and_survives_resource_deletion(
        self,
    ):
        _, _, prepared = self.seed(4275)
        result = complete(
            self.store,
            self.account,
            self.generation,
            prepared,
            operation_id="resource-provenance-success",
            stage=1,
            creation_time=123,
            result_prefix=(0, 1),
            success=True,
            probability=1,
        )
        self.assertTrue(result["success"])
        resource_uid = result["resource"]["resource_uid"]
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT resource_uid,resource FROM planting_receipts WHERE operation_id=%s",
                ("resource-provenance-success",),
            ).fetchone()
            self.assertEqual(receipt["resource_uid"], resource_uid)
            self.assertEqual(receipt["resource"]["resource_uid"], resource_uid)

            with self.assertRaises(UniqueViolation):
                with db.transaction():
                    db.execute(
                        "INSERT INTO planting_receipts(operation_id,character_id,item_uid,request,resource,success,probability) "
                        "VALUES(%s,%s,%s,%s,%s,TRUE,1)",
                        (
                            "resource-provenance-duplicate",
                            self.char["id"],
                            999999,
                            Jsonb({}),
                            Jsonb({"resource_uid": resource_uid}),
                        ),
                    )

            for resource in ({}, {"resource_uid": -4}):
                with self.subTest(resource=resource), self.assertRaises(CheckViolation):
                    with db.transaction():
                        db.execute(
                            "INSERT INTO planting_receipts(operation_id,character_id,item_uid,request,resource,success,probability) "
                            "VALUES(%s,%s,%s,%s,%s,TRUE,1)",
                            (
                                "resource-provenance-invalid",
                                self.char["id"],
                                999999,
                                Jsonb({}),
                                Jsonb(resource),
                            ),
                        )

            with self.assertRaises(GeneratedAlways):
                with db.transaction():
                    db.execute(
                        "INSERT INTO planting_receipts(operation_id,character_id,item_uid,request,resource,resource_uid,success,probability) "
                        "VALUES(%s,%s,%s,%s,%s,%s,TRUE,1)",
                        (
                            "resource-provenance-explicit",
                            self.char["id"],
                            999999,
                            Jsonb({}),
                            Jsonb({"resource_uid": resource_uid + 1}),
                            resource_uid,
                        ),
                    )

            db.execute(
                "DELETE FROM planted_resources WHERE resource_uid=%s", (resource_uid,)
            )
            retained = db.execute(
                "SELECT resource_uid FROM planting_receipts WHERE operation_id=%s",
                ("resource-provenance-success",),
            ).fetchone()
            self.assertEqual(retained["resource_uid"], resource_uid)

    def test_failure_receipt_generated_resource_uid_is_null(self):
        _, _, prepared = self.seed(4275)
        complete(
            self.store,
            self.account,
            self.generation,
            prepared,
            operation_id="resource-provenance-failure",
            stage=1,
            creation_time=123,
            result_prefix=(0, 1),
            success=False,
            probability=0,
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT success,resource_uid FROM planting_receipts WHERE operation_id=%s",
                ("resource-provenance-failure",),
            ).fetchone()
        self.assertFalse(row["success"])
        self.assertIsNone(row["resource_uid"])

    def test_probability_zero_fails_and_one_succeeds_with_persisted_value(self):
        _, _, prepared = self.seed(4275)
        with patch("wakfu_server.planting.secrets.randbelow", return_value=0) as draw:
            failed = complete(
                self.store,
                self.account,
                self.generation,
                prepared,
                operation_id="probability-zero",
                stage=1,
                creation_time=123,
                result_prefix=(0, 1),
                probability=0,
            )
        draw.assert_called_once_with(1 << 53)
        self.assertFalse(failed["success"])
        self.assertEqual(failed["probability"], 0)
        self.assertIsNone(failed["resource"])
        self.assertEqual(
            [packet[0] for packet in failed["packets"]], [12954, 12470, 349]
        )

        with patch(
            "wakfu_server.planting.secrets.randbelow", return_value=(1 << 53) - 1
        ) as draw:
            succeeded = complete(
                self.store,
                self.account,
                self.generation,
                prepared,
                operation_id="probability-one",
                stage=1,
                creation_time=123,
                result_prefix=(0, 1),
                probability=1,
            )
        draw.assert_called_once_with(1 << 53)
        self.assertTrue(succeeded["success"])
        self.assertEqual(succeeded["probability"], 1)
        self.assertIsNotNone(succeeded["resource"])
        self.assertEqual(succeeded["packets"][0][0], 13135)
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT operation_id,success,probability FROM planting_receipts ORDER BY operation_id"
            ).fetchall()
            self.assertEqual(
                rows,
                [
                    {
                        "operation_id": "probability-one",
                        "success": True,
                        "probability": 1.0,
                    },
                    {
                        "operation_id": "probability-zero",
                        "success": False,
                        "probability": 0.0,
                    },
                ],
            )

    def test_probability_uses_strict_boundary_and_retry_reuses_saved_outcome(self):
        item, _, prepared = self.seed(4275)

        def prepare_at(x, y):
            body = struct.pack(">iqii", SEEDS[4275]["action_id"], item["uid"], x, y)
            return prepare(
                self.store,
                self.account,
                self.generation,
                self.char,
                body,
                authorize_cell=lambda *args: 0,
            )

        draw_value = 1 << 51  # exactly 0.25 of the 53-bit uniform range
        with patch(
            "wakfu_server.planting.secrets.randbelow", return_value=draw_value
        ) as draw:
            boundary = complete(
                self.store,
                self.account,
                self.generation,
                prepared,
                operation_id="probability-boundary",
                stage=1,
                creation_time=123,
                result_prefix=(0, 1),
                probability=0.25,
            )
        draw.assert_called_once_with(1 << 53)
        self.assertFalse(boundary["success"])
        self.assertEqual(boundary["probability"], 0.25)

        below_prepared = prepare_at(12, 13)
        with patch(
            "wakfu_server.planting.secrets.randbelow",
            return_value=(1 << 51) - 1,
        ) as draw:
            below = complete(
                self.store,
                self.account,
                self.generation,
                below_prepared,
                operation_id="probability-below-boundary",
                stage=1,
                creation_time=123,
                result_prefix=(0, 1),
                probability=0.25,
            )
        draw.assert_called_once_with(1 << 53)
        self.assertTrue(below["success"])

        retry_prepared = prepare_at(14, 15)
        with patch("wakfu_server.planting.secrets.randbelow", return_value=0) as draw:
            first = complete(
                self.store,
                self.account,
                self.generation,
                retry_prepared,
                operation_id="probability-retry",
                stage=1,
                creation_time=123,
                result_prefix=(0, 1),
                probability=0,
            )
        self.assertFalse(first["success"])
        draw.assert_called_once_with(1 << 53)
        with patch(
            "wakfu_server.planting.secrets.randbelow",
            side_effect=AssertionError("retry must not draw again"),
        ) as retry_draw:
            replay = complete(
                self.store,
                self.account,
                self.generation,
                retry_prepared,
                operation_id="probability-retry",
                stage=1,
                creation_time=123,
                result_prefix=(0, 1),
                probability=1,
            )
        retry_draw.assert_not_called()
        self.assertTrue(replay["duplicate"])
        self.assertFalse(replay["success"])
        self.assertEqual(replay["probability"], 0.0)
        self.assertEqual(replay["packets"], [])
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"],
            [],
        )

    def test_occupied_cell_rejects_second_actor_before_probability_draw_or_consume(
        self,
    ):
        item, _, owner_prepared = self.seed(4275)
        foreign_account = self.store.register("planting-cell-other", "password")["id"]
        foreign_char = self.store.create_character(foreign_account, "Cell Planter")
        foreign_generation = self.store.begin_session(foreign_account)
        self.store.select_character(
            foreign_account, foreign_generation, foreign_char["id"]
        )
        foreign_item = grant(
            self.store,
            foreign_account,
            foreign_generation,
            foreign_char["id"],
            reference=4275,
            quantity=3,
            container=foreign_char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=SEEDS,
        )
        ensure_learned(
            self.store,
            foreign_account,
            foreign_generation,
            foreign_char["id"],
            [SEEDS[4275]["profession_id"]],
        )
        foreign_body = struct.pack(
            ">iqii", SEEDS[4275]["action_id"], foreign_item["uid"], 10, 11
        )
        foreign_prepared = prepare(
            self.store,
            foreign_account,
            foreign_generation,
            foreign_char,
            foreign_body,
            authorize_cell=lambda *args: 0,
        )
        self.assertEqual(
            (
                owner_prepared["character"]["map_id"],
                owner_prepared["character"]["instance_id"],
            ),
            (
                foreign_prepared["character"]["map_id"],
                foreign_prepared["character"]["instance_id"],
            ),
        )

        complete(
            self.store,
            self.account,
            self.generation,
            owner_prepared,
            operation_id="cell-owner-success",
            stage=1,
            creation_time=123,
            result_prefix=(0, 1),
        )
        with patch(
            "wakfu_server.planting.secrets.randbelow",
            side_effect=AssertionError("occupied cell must reject before RNG"),
        ) as draw:
            with self.assertRaises(ValueError):
                complete(
                    self.store,
                    foreign_account,
                    foreign_generation,
                    foreign_prepared,
                    operation_id="cell-foreign-failure",
                    stage=1,
                    creation_time=123,
                    result_prefix=(0, 1),
                    probability=0,
                )
        draw.assert_not_called()
        self.assertEqual(
            self.store.character(foreign_account, foreign_char["id"])[
                "inventory_items"
            ][0]["quantity"],
            3,
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM planting_receipts").fetchone()[
                    "count"
                ],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM profession_xp_receipts WHERE account_id=%s",
                    (foreign_account,),
                ).fetchone()["count"],
                0,
            )

    def test_invalid_probability_types_and_ranges_reject_before_rng_or_mutation(self):
        _, _, prepared = self.seed(4275)
        invalid = (True, False, "0.5", -0.01, 1.01, float("nan"), float("inf"))
        with patch(
            "wakfu_server.planting.secrets.randbelow",
            side_effect=AssertionError("invalid probability must not draw"),
        ) as draw:
            for index, probability in enumerate(invalid):
                with self.subTest(probability=repr(probability)):
                    with self.assertRaises(ValueError):
                        complete(
                            self.store,
                            self.account,
                            self.generation,
                            prepared,
                            operation_id=f"invalid-probability-{index}",
                            stage=1,
                            creation_time=123,
                            result_prefix=(0, 1),
                            probability=probability,
                        )
        draw.assert_not_called()
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            3,
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM planting_receipts").fetchone()[
                    "count"
                ],
                0,
            )

    def test_probability_sql_constraint_rejects_nan_and_out_of_bounds_values(self):
        _, _, prepared = self.seed(4275)
        complete(
            self.store,
            self.account,
            self.generation,
            prepared,
            operation_id="probability-sql-check",
            stage=1,
            creation_time=123,
            result_prefix=(0, 1),
            probability=0,
        )
        invalid_values = ("NaN", -0.01, 1.01)
        with self.store.connection() as db:
            for value in invalid_values:
                with self.subTest(value=value):
                    with self.assertRaises(CheckViolation):
                        with db.transaction():
                            db.execute(
                                "UPDATE planting_receipts SET probability=%s WHERE operation_id=%s",
                                (value, "probability-sql-check"),
                            )

    def test_herbalist_resource_and_owned_consumption_once(self):
        item, body, p = self.seed(4275)
        kwargs = dict(
            operation_id="herb-1", stage=1, creation_time=123, result_prefix=(0, 1)
        )
        result = complete(self.store, self.account, self.generation, p, **kwargs)
        self.assertEqual(
            [packet[0] for packet in result["packets"]], [13135, 12954, 12470, 349]
        )
        self.assertEqual(
            result["packets"][2], (12470, struct.pack(">qh", item["uid"], -1))
        )
        self.assertEqual(result["resource"]["resource_reference"], 60)
        duplicate = complete(self.store, self.account, self.generation, p, **kwargs)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["packets"], [])
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            2,
        )

    def test_monster_native_family_and_outbox_retry(self):
        item, body, p = self.seed(30927)
        member = owned_instance(
            5525, 1, -2000, map_id=self.char["map_id"], x=10, y=11, z=0
        )
        planted = complete(
            self.store,
            self.account,
            self.generation,
            p,
            operation_id="monster-1",
            stage=1,
            creation_time=123,
            result_prefix=(0, 1),
            monster_members=[member],
            group_id=2000,
        )
        self.assertEqual(
            "monster_seed_not_living_population", planted["ecology"]["reason"]
        )
        self.assertEqual(
            [packet for packet in planted["packets"] if packet[0] == 349],
            [
                information(
                    "Ecosistema: semilla de monstruo plantada. Todavía no cuenta como "
                    "población viva; la afinidad se evalúa cuando nace el monstruo."
                )
            ],
        )
        self.assertNotIn(13574, [opcode for opcode, _ in planted["packets"]])
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM personal_ecology_receipts WHERE character_id=%s",
                    (self.char["id"],),
                ).fetchone()["n"],
            )

        class Failed:
            def register(self, *args):
                raise ConnectionError("Group registry unavailable")

        with self.assertRaises(ConnectionError):
            publish_groups(self.store, Failed())
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            2,
        )
        groups = Groups()
        self.assertEqual(publish_groups(self.store, groups)[0][0], 12608)
        self.assertEqual(publish_groups(self.store, groups), [])
        self.assertEqual(len(groups.available(self.char["map_id"], 0)), 1)

    def test_bad_stage_rolls_back_and_unlearned_rejected(self):
        item, body, p = self.seed(4275)
        with self.assertRaises(ValueError):
            complete(
                self.store,
                self.account,
                self.generation,
                p,
                operation_id="bad",
                stage=127,
                creation_time=1,
                result_prefix=(0, 1),
            )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            3,
        )
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM account_professions WHERE account_id=%s", (self.account,)
            )
        with self.assertRaises(ValueError):
            prepare(
                self.store,
                self.account,
                self.generation,
                self.char,
                body,
                authorize_cell=lambda *args: 0,
            )
