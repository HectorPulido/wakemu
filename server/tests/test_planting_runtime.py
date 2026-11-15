import ast
import struct
import unittest
from unittest.mock import patch
from source_view import WorldSourcePath as Path
from postgres_case import PostgresCase
from wakfu_server.planting_runtime import Plantings
from wakfu_server import planting as planting_api
from wakfu_server.planting import SEEDS
from wakfu_server.inventory_items import grant
from wakfu_server.profession_store import ensure_learned
from wakfu_server.combat_groups import Groups
from wakfu_server.combat_group_store import PersistentGroups
from psycopg.types.json import Jsonb
from wakfu_server.profession_wire import MAX_XP
from planting_fixture import prepare, begin_prepared
from wakfu_server.planting_bonus import current as current_planting_bonus
from wakfu_server.territory_weather import save as save_territory_weather
from wakfu_server.ecology_feedback import information
from wakfu_server.planting_cells import cells


class RuntimePlantingTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = [1000.0]
        self.store.clock = lambda: self.now[0]
        self.account = self.store.register("runtime-planter", "local-password")["id"]
        self.char = self.store.create_character(self.account, "Runtime Planter")
        self.gen = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.gen, self.char["id"])
        self.runtime = Plantings(self.store)
        self.groups = Groups()
        self.deliveries = []

    def publish(self, delivery):
        self.deliveries.append(delivery)

    def seed(self, ref):
        ensure_learned(
            self.store,
            self.account,
            self.gen,
            self.char["id"],
            [SEEDS[ref]["profession_id"]],
        )
        item = grant(
            self.store,
            self.account,
            self.gen,
            self.char["id"],
            reference=ref,
            quantity=2,
            container=self.char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=SEEDS,
        )
        return struct.pack(">iqii", SEEDS[ref]["action_id"], item["uid"], 10, 11)

    def begin(self, body, *, probability=1.0, z=0):
        return begin_prepared(
            self.runtime,
            self.account,
            self.gen,
            self.char,
            body,
            lambda *args: z,
            probability=probability,
        )

    def begin_at_native_ground(self, body, *, probability=1.0):
        return self.begin(body, probability=probability, z=70)

    def finish(self):
        return self.runtime.complete(self.account, self.gen, self.char, b"\x02\x00\x02")

    def native_probability_body(self, item_reference):
        body = self.seed(item_reference)
        action, uid, _, _ = struct.unpack(">iqii", body)
        return struct.pack(">iqii", action, uid, -23, -143)

    def save_native_territory_weather(self, weather_id):
        payload = struct.pack(">qb6fi", 79201, 0, 1, 2, 3, 4, 5, 6, weather_id)
        return save_territory_weather(
            self.store,
            map_id=1134,
            instance_id=self.char["instance_id"],
            region_id=79201,
            payload=payload,
        )

    def assert_native_planting_modifier(self):
        from wakfu_server.territory_bonuses import current_region, profession_xp_percent

        with self.store.connection() as db:
            character = self.store.character(self.account, self.char["id"], db)
            self.assertEqual(
                profession_xp_percent(current_region(db, character), "planting"), -10
            )

    def test_owned_herb_start_finish_snapshots_and_local_growth(self):
        body = self.seed(4275)
        self.assert_native_planting_modifier()
        opcode, raw = self.begin(body)
        ticket = self.runtime.pending[self.char["id"]]
        self.assertEqual(opcode, 12815)
        self.assertEqual(
            struct.unpack(">Bhqiiiii", raw)[:6], (1, 2, self.char["id"], 72, 3000, 5)
        )
        with self.assertRaises(ValueError):
            self.finish()
        self.now[0] += 3
        result = self.finish()
        self.assertEqual(
            [p[0] for p in result["packets"]], [13135, 12954, 12470, 12916, 349]
        )
        self.assertEqual(struct.unpack(">iq", result["packets"][3][1]), (72, 9))
        self.assertEqual(
            result["packets"][2],
            (
                12470,
                struct.pack(
                    ">qh",
                    self.store.character(self.account, self.char["id"])[
                        "inventory_items"
                    ][0]["uid"],
                    -1,
                ),
            ),
        )
        from wakfu_server import planting

        replay = planting.complete(
            self.store,
            self.account,
            self.gen,
            ticket["prepared"],
            operation_id=ticket["token"],
            stage=1,
            creation_time=int(self.now[0] * 1000),
            result_prefix=(self.char["id"], ticket["prepared"]["request"]["action_id"]),
        )
        self.assertTrue(replay["duplicate"])
        self.assertEqual(replay["packets"], [])
        self.assertFalse(self.finish()["applied"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                    (self.account,),
                ).fetchone()["xp"],
                9,  # Native regional profession modifier is -10%.
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM profession_xp_receipts WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["count"],
                1,
            )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            1,
        )
        scene = tuple(
            ticket["prepared"]["character"][key] for key in ("map_id", "instance_id")
        )
        self.assertEqual(
            tuple(result["resource"][key] for key in ("map_id", "instance_id")), scene
        )
        self.assertEqual(len(self.runtime.snapshots(*scene)), 1)
        self.assertEqual(self.runtime.snapshots(scene[0] + 1, scene[1]), [])
        self.now[0] += 30
        with self.store.connection() as db:
            resource = dict(db.execute("SELECT * FROM planted_resources").fetchone())
            edge = db.execute(
                "SELECT to_stage,delay_ms,probability FROM resource_growth_transitions WHERE resource_reference=60 AND from_stage=1"
            ).fetchone()
        self.runtime.apply_growth_candidates(
            [(resource, planting_api.RESOURCES[60], tuple(edge.values()))]
        )
        result = self.runtime.publish_growth(self.groups, publish=self.publish)
        self.assertEqual([p[0] for p in result[0]["packets"]], [12782])
        self.assertEqual(struct.unpack(">iihhqi", result[0]["packets"][0][1])[3], 2)
        self.assertEqual(self.deliveries, result)
        self.assertEqual(
            self.runtime.publish_growth(self.groups, publish=self.publish), []
        )

    def test_probability_zero_fails_atomically_but_consumes_one_seed_without_xp(self):
        body = self.seed(4275)
        self.begin(body, probability=0.0)
        ticket = self.runtime.pending[self.char["id"]]
        self.assertEqual(ticket["probability"], 0.0)
        self.now[0] += 3

        result = self.finish()

        self.assertFalse(result["success"])
        self.assertIsNone(result["resource"])
        self.assertEqual(result["probability"], 0.0)
        self.assertEqual(
            [packet[0] for packet in result["packets"]], [12954, 12470, 349]
        )
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT success,resource,probability FROM planting_receipts WHERE operation_id=%s",
                (ticket["token"],),
            ).fetchone()
            self.assertFalse(receipt["success"])
            self.assertIsNone(receipt["resource"])
            self.assertEqual(receipt["probability"], 0.0)
            self.assertEqual(
                db.execute("SELECT count(*) FROM planted_resources").fetchone()[
                    "count"
                ],
                0,
            )
            self.assertEqual(
                db.execute("SELECT count(*) FROM profession_xp_receipts").fetchone()[
                    "count"
                ],
                0,
            )
            profession = db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=%s",
                (self.account, SEEDS[4275]["profession_id"]),
            ).fetchone()
            self.assertEqual(profession["xp"], 0)
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            1,
        )

    def test_probability_one_succeeds_and_is_frozen_at_begin(self):
        body = self.seed(4275)
        self.begin(body, probability=1.0)
        ticket = self.runtime.pending[self.char["id"]]
        self.assertEqual(ticket["probability"], 1.0)
        self.now[0] += 3
        result = self.finish()
        self.assertTrue(result["success"])
        self.assertEqual(result["probability"], 1.0)
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT success,probability FROM planting_receipts WHERE operation_id=%s",
                (ticket["token"],),
            ).fetchone()
        self.assertEqual(receipt, {"success": True, "probability": 1.0})

    def test_invalid_prepared_probability_rejects_before_occupation_or_consumption(
        self,
    ):
        body = self.seed(4275)
        for probability in (True, -0.1, 1.1, float("nan"), "0.5"):
            with self.subTest(probability=probability):
                with self.assertRaises(ValueError):
                    self.begin(body, probability=probability)
                self.assertNotIn(self.char["id"], self.runtime.pending)
                self.assertEqual(self.runtime.cells, {})
                self.assertEqual(
                    self.store.character(self.account, self.char["id"])[
                        "inventory_items"
                    ][0]["quantity"],
                    2,
                )

    def test_missing_or_invalid_duration_policy_rejects_before_occupation(self):
        body = self.seed(4275)
        invalid_values = ("3000", True, 0, 300001)
        for value in (None, *invalid_values):
            with self.subTest(value=value):
                self.runtime = Plantings(self.store)
                with self.store.connection() as db:
                    if value is None:
                        db.execute(
                            "DELETE FROM settings WHERE name='planting_duration_ms'"
                        )
                    else:
                        db.execute(
                            "UPDATE settings SET value=%s WHERE name='planting_duration_ms'",
                            (Jsonb(value),),
                        )
                with self.assertRaisesRegex(ValueError, "planting duration"):
                    self.begin(body)
                self.assertNotIn(self.char["id"], self.runtime.pending)
                self.assertEqual(self.runtime.cells, {})
                self.assertEqual(
                    self.store.character(self.account, self.char["id"])[
                        "inventory_items"
                    ][0]["quantity"],
                    2,
                )
                with self.store.connection() as db:
                    self.assertEqual(
                        db.execute("SELECT count(*) FROM planting_receipts").fetchone()[
                            "count"
                        ],
                        0,
                    )
                    self.assertEqual(
                        db.execute("SELECT count(*) FROM planted_resources").fetchone()[
                            "count"
                        ],
                        0,
                    )
                    if value is None:
                        db.execute(
                            "INSERT INTO settings(name,value) VALUES('planting_duration_ms',%s)",
                            (Jsonb(3000),),
                        )

    def test_duration_policy_is_frozen_per_ticket_and_next_occupation_uses_new_value(
        self,
    ):
        body = self.seed(4275)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='planting_duration_ms'",
                (Jsonb(3000),),
            )
        _, packet = self.begin(body)
        ticket = self.runtime.pending[self.char["id"]]
        started = ticket["started"]
        self.assertEqual(ticket["duration_ms"], 3000)
        self.assertEqual(struct.unpack(">Bhqiiiii", packet)[4], 3000)

        # Shortening policy after begin must not shorten this accepted ticket.
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='planting_duration_ms'",
                (Jsonb(1000),),
            )
        self.now[0] += 2.8
        with self.assertRaisesRegex(ValueError, "before native occupation duration"):
            self.finish()
        self.assertEqual(self.runtime.pending[self.char["id"]]["started"], started)
        self.assertEqual(self.runtime.pending[self.char["id"]]["duration_ms"], 3000)
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            2,
        )
        self.now[0] += 0.3
        self.assertTrue(self.finish()["success"])

        # The subsequent occupation reads the new database value and can use
        # the remaining seed on a distinct cell.
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='planting_duration_ms'",
                (Jsonb(2000),),
            )
        item_uid = self.store.character(self.account, self.char["id"])[
            "inventory_items"
        ][0]["uid"]
        second_body = struct.pack(">iqii", SEEDS[4275]["action_id"], item_uid, 12, 13)
        _, next_packet = self.begin(second_body)
        next_ticket = self.runtime.pending[self.char["id"]]
        self.assertEqual(next_ticket["duration_ms"], 2000)
        self.assertEqual(struct.unpack(">Bhqiiiii", next_packet)[4], 2000)
        self.assertEqual(next_ticket["started"], self.now[0])

    def test_cancel_after_probability_resolution_does_not_roll_or_consume(self):
        body = self.seed(4275)
        self.begin(body)
        with patch.object(
            planting_api.secrets,
            "randbelow",
            side_effect=AssertionError("RNG used on cancel"),
        ) as draw:
            self.assertTrue(self.runtime.cancel(self.char["id"], self.gen))
        draw.assert_not_called()
        self.assertNotIn(self.char["id"], self.runtime.pending)
        self.assertEqual(self.runtime.cells, {})
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            2,
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM planting_receipts").fetchone()[
                    "count"
                ],
                0,
            )
            self.assertEqual(
                db.execute("SELECT count(*) FROM planted_resources").fetchone()[
                    "count"
                ],
                0,
            )

    def test_external_probability_is_committed_without_python_resolution(self):
        body = self.native_probability_body(4444)
        self.runtime = Plantings(self.store, open_test_policy=True)
        self.begin_at_native_ground(body, probability=0.56)
        ticket = self.runtime.pending[self.char["id"]]
        self.now[0] += ticket["duration_ms"] / 1000
        with patch.object(planting_api.secrets, "randbelow", return_value=0):
            result = self.finish()
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["probability"], 0.56)
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT success,resource,probability FROM planting_receipts WHERE operation_id=%s",
                (ticket["token"],),
            ).fetchone()
        self.assertTrue(receipt["success"])
        self.assertIsNotNone(receipt["resource"])
        self.assertAlmostEqual(receipt["probability"], 0.56)

    def test_missing_prepared_probability_rejects_without_charge(self):
        body = self.seed(4275)
        prepared = prepare(
            self.store,
            self.account,
            self.gen,
            self.char,
            body,
            authorize_cell=lambda *args: 0,
        )
        del prepared["probability"]
        with self.assertRaises(KeyError):
            self.runtime.begin_prepared(
                self.account, self.gen, self.char, body, prepared, lambda *args: 0
            )
        self.assertEqual(self.runtime.pending, {})
        self.assertEqual(self.runtime.cells, {})
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            2,
        )

    def test_monster_growth_requires_an_external_prepared_member(self):
        reference = SEEDS[30927]["resource_reference"]
        resource = dict(
            resource_uid=9007,
            map_id=1134,
            instance_id=0,
            x=10,
            y=11,
            z=0,
            resource_reference=reference,
            stage=1,
            creation_time=0,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource.values()),
            )
        with self.assertRaisesRegex(ValueError, "Prepared native monster member"):
            self.runtime.apply_growth_candidates(
                [(resource, planting_api.RESOURCES[reference], None)]
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM planted_resources WHERE resource_uid=9007"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM planting_growth_outbox"
                ).fetchone()["n"],
                0,
            )

    def test_python_planner_entry_points_are_absent(self):
        self.assertFalse(hasattr(self.runtime, "begin"))
        self.assertFalse(hasattr(self.runtime, "mature"))
        self.assertFalse(hasattr(planting_api, "prepare"))

    def test_seed_monster_growth_and_redis_retry_are_idempotent(self):
        point = next(
            (x, y, row["z"])
            for (x, y), rows in cells(1134).items()
            for row in rows
            if row["region_id"] == 79001
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (*point, self.char["id"]),
            )
        self.char = self.store.character(self.account, self.char["id"])
        body = self.seed(30927)
        action_id, uid, _, _ = struct.unpack(">iqii", body)
        body = struct.pack(">iqii", action_id, uid, point[0], point[1])
        begin_prepared(
            self.runtime,
            self.account,
            self.gen,
            self.char,
            body,
            lambda _a, _r, _s, _d: point[2],
        )
        self.now[0] += 3
        planted = self.finish()
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
        self.now[0] += 30

        groups = PersistentGroups(self.store)

        failed_deliveries = []

        def broken_publish(delivery):
            failed_deliveries.append(delivery)
            raise ConnectionError("Redis unavailable")

        from wakfu_server.monsters import owned_instance, REFERENCES

        with self.store.connection() as db:
            resource = dict(db.execute("SELECT * FROM planted_resources").fetchone())
        member = owned_instance(
            5455,
            REFERENCES[5455]["min_level"],
            -1,
            map_id=resource["map_id"],
            instance_id=resource["instance_id"],
            x=resource["x"],
            y=resource["y"],
            z=resource["z"],
        )
        self.runtime.apply_growth_candidates(
            [(resource, planting_api.RESOURCES[resource["resource_reference"]], None)],
            prepared_members={resource["resource_uid"]: member},
        )
        with self.assertRaises(ConnectionError):
            self.runtime.publish_growth(groups, publish=broken_publish)
        self.assertEqual(failed_deliveries[0]["ecology"]["reason"], "applied")
        self.assertEqual(
            [p[0] for p in failed_deliveries[0]["ecology"]["packets"]], [13574]
        )
        self.assertTrue(failed_deliveries[0]["ecology"]["information"])
        self.assertEqual(self.runtime.snapshots(1134, 0), [])
        with self.assertRaisesRegex(ValueError, "Growth publication"):
            begin_prepared(
                self.runtime,
                self.account,
                self.gen,
                self.char,
                body,
                lambda _a, _r, _s, _d: point[2],
            )
        result = self.runtime.publish_growth(groups, publish=self.publish)
        self.assertEqual([p[0] for p in result[0]["packets"]], [12782, 12608])
        self.assertEqual(struct.unpack(">iihhqi", result[0]["packets"][0][1])[3], 0)
        self.assertEqual(result[0]["ecology"]["reason"], "already_activated")
        self.assertEqual([p[0] for p in result[0]["ecology"]["packets"]], [13574])
        self.assertNotIn("information", result[0]["ecology"])
        with self.store.connection() as db:
            pending = db.execute(
                "SELECT group_payload FROM planting_growth_outbox "
                "WHERE group_payload IS NOT NULL"
            ).fetchall()
        self.assertEqual(1, len(pending))
        expected_ref = pending[0]["group_payload"]["members"][0]["ref"]
        self.assertIn(expected_ref, (5455, 5456))
        available = groups.available(1134, 0)
        self.assertEqual(len(available), 1)
        self.assertEqual(available[0]["members"][0]["ref"], expected_ref)
        self.assertEqual(self.runtime.publish_growth(groups, publish=self.publish), [])
        self.assertEqual(
            Plantings(self.reopen()).publish_growth(self.groups, publish=self.publish),
            [],
        )

    def insert_pending_growth(self, *, resource_uid=9003, stage=3):
        resource = dict(
            resource_uid=resource_uid,
            map_id=1134,
            instance_id=0,
            x=21,
            y=32,
            z=1,
            resource_reference=60,
            stage=stage,
            creation_time=123456,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) "
                "VALUES(%s,%s,NULL)",
                (resource_uid, Jsonb(resource)),
            )
        return resource

    def test_publish_failure_keeps_event_pending_and_retry_replays_exact_delivery(self):
        self.insert_pending_growth(resource_uid=9003, stage=3)
        attempted = []

        def fail(delivery):
            attempted.append(delivery)
            raise ConnectionError("world delivery unavailable")

        with self.assertRaisesRegex(ConnectionError, "world delivery unavailable"):
            self.runtime.publish_growth(self.groups, publish=fail)
        with self.store.connection() as db:
            self.assertFalse(
                db.execute(
                    "SELECT published FROM planting_growth_outbox WHERE resource_uid=9003"
                ).fetchone()["published"]
            )

        retried = []

        def retry(delivery):
            retried.append(delivery)
            with self.store.connection() as db:
                self.assertFalse(
                    db.execute(
                        "SELECT published FROM planting_growth_outbox WHERE resource_uid=9003"
                    ).fetchone()["published"]
                )

        published = self.runtime.publish_growth(self.groups, publish=retry)
        self.assertEqual(attempted, retried)
        self.assertEqual(published, retried)
        with self.store.connection() as db:
            self.assertTrue(
                db.execute(
                    "SELECT published FROM planting_growth_outbox WHERE resource_uid=9003"
                ).fetchone()["published"]
            )

    def test_growth_callback_sees_pending_event_and_packet_uses_payload_stage(self):
        self.insert_pending_growth(resource_uid=9004, stage=3)
        observed = []

        def publish_and_inspect(delivery):
            observed.append(delivery)
            with self.store.connection() as db:
                self.assertFalse(
                    db.execute(
                        "SELECT published FROM planting_growth_outbox WHERE resource_uid=9004"
                    ).fetchone()["published"]
                )

        result = self.runtime.publish_growth(self.groups, publish=publish_and_inspect)
        self.assertEqual(result, observed)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["packets"][0][0], 12782)
        self.assertEqual(struct.unpack(">iihhqi", result[0]["packets"][0][1])[3], 3)
        with self.store.connection() as db:
            self.assertTrue(
                db.execute(
                    "SELECT published FROM planting_growth_outbox WHERE resource_uid=9004"
                ).fetchone()["published"]
            )

    def test_world_growth_uses_only_the_durable_publisher(self):
        from wakfu_server import ecology_plants

        source = __import__("inspect").getsource(ecology_plants)
        self.assertIn("publish_growth", source)
        self.assertNotIn(".mature(", source)

    def test_generation_fencing_cancel_and_takeover(self):
        body = self.seed(4275)
        self.begin(body)
        old = self.gen
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET expires_at=TIMESTAMPTZ '1970-01-01 00:00:00+00' WHERE account_id=%s",
                (self.account,),
            )
        self.gen = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.gen, self.char["id"])
        self.begin(body)
        self.assertFalse(self.runtime.cancel(self.char["id"], old))
        self.now[0] += 3
        self.assertTrue(self.finish()["applied"])

    def test_cancel_and_replay_emit_no_delta_then_last_unit_deletes(self):
        body = self.seed(4275)
        self.begin(body)
        cancelled = self.runtime.complete(
            self.account, self.gen, self.char, b"\x03\x00\x02"
        )
        self.assertFalse(cancelled["applied"])
        self.assertEqual(cancelled["packets"], [])
        self.assertFalse(self.finish()["applied"])
        self.assertEqual(self.finish()["packets"], [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                    (self.account,),
                ).fetchone()["xp"],
                0,
            )
        self.begin(body)
        self.now[0] += 3
        first = self.finish()
        item = self.store.character(self.account, self.char["id"])["inventory_items"][0]
        self.assertEqual(
            first["packets"][2], (12470, struct.pack(">qh", item["uid"], -1))
        )
        self.assertEqual(item["quantity"], 1)

        last_body = struct.pack(">iqii", SEEDS[4275]["action_id"], item["uid"], 12, 11)
        self.begin(last_body)
        self.now[0] += 3
        last = self.finish()
        self.assertEqual(
            [packet[0] for packet in last["packets"]], [13135, 12954, 12470, 12916, 349]
        )
        self.assertEqual(
            last["packets"][2], (12470, struct.pack(">qh", item["uid"], -1))
        )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"], []
        )
        self.assertFalse(self.finish()["applied"])
        self.assertEqual(self.finish()["packets"], [])

    def test_planting_reward_multiplier_cap_and_packet_are_atomic(self):
        body = self.seed(4275)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='profession_xp'",
                (Jsonb({"multiplier_basis_points": 20000}),),
            )
            db.execute(
                "UPDATE account_professions SET xp=%s WHERE account_id=%s AND profession_id=72",
                (MAX_XP - 3, self.account),
            )
        self.begin(body)
        self.now[0] += 3
        result = self.finish()
        self.assertIn((12916, struct.pack(">iq", 72, 3)), result["packets"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                    (self.account,),
                ).fetchone()["xp"],
                MAX_XP,
            )

    def test_invalid_reward_policy_rolls_back_seed_resource_and_both_receipts(self):
        body = self.seed(4275)
        self.begin(body)
        self.now[0] += 3
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='profession_action_rewards'",
                (
                    Jsonb(
                        {
                            "version": 1,
                            "planting_xp": True,
                            "harvest_xp": 50,
                            "recipe_slot_xp": 100,
                        }
                    ),
                ),
            )
        with self.assertRaisesRegex(ValueError, "action reward policy"):
            self.finish()
        saved = self.store.character(self.account, self.char["id"])
        self.assertEqual(saved["inventory_items"][0]["quantity"], 2)
        self.assertEqual(self.runtime.snapshots(1134, 0), [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM planting_receipts").fetchone()[
                    "count"
                ],
                0,
            )
            self.assertEqual(
                db.execute("SELECT count(*) FROM profession_xp_receipts").fetchone()[
                    "count"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                    (self.account,),
                ).fetchone()["xp"],
                0,
            )
        self.assertIn(self.char["id"], self.runtime.pending)
        # The operation token remains retryable once the policy is repaired.
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='profession_action_rewards'",
                (
                    Jsonb(
                        {
                            "version": 1,
                            "planting_xp": 10,
                            "harvest_xp": 50,
                            "recipe_slot_xp": 100,
                        }
                    ),
                ),
            )
        self.assertTrue(self.finish()["applied"])

    def test_planting_receipt_accepts_full_128_character_operation_id(self):
        from wakfu_server import planting

        body = self.seed(4275)
        self.assert_native_planting_modifier()
        self.begin(body)
        prepared = self.runtime.pending[self.char["id"]]["prepared"]
        operation_id = "p" * 128
        result = planting.complete(
            self.store,
            self.account,
            self.gen,
            prepared,
            operation_id=operation_id,
            stage=1,
            creation_time=123456,
            result_prefix=(self.char["id"], prepared["request"]["action_id"]),
        )
        self.assertFalse(result["duplicate"])
        self.assertIn((12916, struct.pack(">iq", 72, 9)), result["packets"])
        with self.store.connection() as db:
            row = db.execute(
                "SELECT operation_id FROM planting_receipts WHERE operation_id=%s",
                (operation_id,),
            ).fetchone()
        self.assertEqual(row["operation_id"], operation_id)
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            1,
        )

    def test_open_local_policy_bypasses_minimum_level_without_granting_items(self):
        body = self.seed(1750)
        with self.assertRaises(ValueError):
            self.begin(body)
        self.runtime = Plantings(self.store, open_test_policy=True)
        self.begin(body)
        self.now[0] += 3
        self.finish()
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            1,
        )

    def test_open_local_policy_still_rejects_unlearned_profession_without_side_effects(
        self,
    ):
        body = self.seed(1750)
        profession_id = SEEDS[1750]["profession_id"]
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM account_professions WHERE account_id=%s AND profession_id=%s",
                (self.account, profession_id),
            )
        self.runtime = Plantings(self.store, open_test_policy=True)
        with self.assertRaisesRegex(ValueError, "Profession unlearned"):
            self.begin(body)
        saved = self.store.character(self.account, self.char["id"])
        self.assertEqual(saved["inventory_items"][0]["quantity"], 2)
        self.assertNotIn(self.char["id"], self.runtime.pending)
        self.assertEqual(self.runtime.snapshots(1134, 0), [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM profession_xp_receipts WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["count"],
                0,
            )

    def test_cardo_and_ash_resource_packets_preserve_public_owner_and_snapshots(self):
        from wakfu_server import planting
        from wakfu_server.wire import proto_fields

        self.assertEqual(planting.SEEDS[4275]["resource_reference"], 60)
        self.assertEqual(planting.SEEDS[8063]["resource_reference"], 139)
        rows = (
            dict(
                resource_uid=9001,
                map_id=1134,
                instance_id=0,
                x=1,
                y=2,
                z=0,
                resource_reference=60,  # Cardo borriquero, native probe fixture.
                stage=2,
                creation_time=1791072000000,
            ),
            dict(
                resource_uid=9002,
                map_id=1134,
                instance_id=0,
                x=34,
                y=12,
                z=1,
                resource_reference=139,  # Esqueje de fresno.
                stage=1,
                creation_time=1791072000000,
            ),
        )

        expected_packets = []
        for resource in rows:
            opcode, body = planting.resource_packet(resource)
            self.assertEqual(opcode, 13135)
            fields = {tag >> 3: value for tag, value in proto_fields(body)}
            self.assertEqual(
                fields,
                {
                    1: resource["resource_reference"],
                    2: resource["x"],
                    3: resource["y"],
                    4: resource["z"],
                    5: resource["stage"],
                    6: 0,
                    7: 0,  # Public resource ownerAccount, never creation_time.
                    8: 0,  # Public resource ownerNation.
                },
            )
            self.assertGreater(resource["creation_time"], 0)
            expected_packets.append((opcode, body))

        with self.store.connection() as db:
            for resource in rows:
                db.execute(
                    """
                    INSERT INTO planted_resources(
                        resource_uid,map_id,instance_id,x,y,z,
                        resource_reference,stage,creation_time
                    ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    tuple(
                        resource[key]
                        for key in (
                            "resource_uid",
                            "map_id",
                            "instance_id",
                            "x",
                            "y",
                            "z",
                            "resource_reference",
                            "stage",
                            "creation_time",
                        )
                    ),
                )
        self.assertEqual(self.runtime.snapshots(1134, 0), expected_packets)

    def test_spawn_occupation_blocks_and_movement_rejects_without_consumption(self):
        body = self.seed(4275)
        self.begin(body)
        with self.assertRaises(ValueError):
            self.begin(body)
        self.now[0] += 3
        with self.store.connection() as db:
            db.execute("UPDATE characters SET x=x+1 WHERE id=%s", (self.char["id"],))
        with self.assertRaises(ValueError):
            self.finish()
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            2,
        )
