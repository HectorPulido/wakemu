import ast
import struct
import unittest
from pathlib import Path
from postgres_case import PostgresCase
from wakfu_server.planting_runtime import Plantings
from wakfu_server.planting import SEEDS
from wakfu_server.inventory_items import grant
from wakfu_server.profession_store import ensure_learned
from wakfu_server.combat_groups import Groups
from psycopg.types.json import Jsonb


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

    def begin(self, body):
        return self.runtime.begin(
            self.account, self.gen, self.char, body, lambda *args: 0
        )

    def finish(self):
        return self.runtime.complete(self.account, self.gen, self.char, b"\x02\x00\x02")

    def test_owned_herb_start_finish_snapshots_and_local_growth(self):
        body = self.seed(4275)
        opcode, raw = self.begin(body)
        self.assertEqual(opcode, 12815)
        self.assertEqual(
            struct.unpack(">Bhqiiiii", raw)[:6], (1, 2, self.char["id"], 72, 3000, 5)
        )
        with self.assertRaises(ValueError):
            self.finish()
        self.now[0] += 3
        result = self.finish()
        self.assertEqual([p[0] for p in result["packets"]], [13135, 12954, 12470])
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
        self.assertFalse(self.finish()["applied"])
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            1,
        )
        self.assertEqual(len(self.runtime.snapshots(1134, 0)), 1)
        self.assertEqual(self.runtime.snapshots(1385, 0), [])
        self.now[0] += 30
        result = self.runtime.mature(self.groups, publish=self.publish)
        self.assertEqual([p[0] for p in result[0]["packets"]], [12782])
        self.assertEqual(struct.unpack(">iihhqi", result[0]["packets"][0][1])[3], 2)
        self.assertEqual(self.deliveries, result)
        self.assertEqual(self.runtime.mature(self.groups, publish=self.publish), [])

    def test_seed_monster_growth_and_redis_retry_are_idempotent(self):
        self.begin(self.seed(30927))
        self.now[0] += 3
        self.finish()
        self.now[0] += 30

        class Broken:
            def register(self, *args):
                raise ConnectionError("Redis unavailable")

        with self.assertRaises(ConnectionError):
            self.runtime.mature(Broken(), publish=self.publish)
        self.assertEqual(self.runtime.snapshots(1134, 0), [])
        with self.assertRaisesRegex(ValueError, "Growth publication"):
            self.begin(
                struct.pack(
                    ">iqii",
                    SEEDS[30927]["action_id"],
                    self.store.character(self.account, self.char["id"])[
                        "inventory_items"
                    ][0]["uid"],
                    10,
                    11,
                )
            )
        result = self.runtime.publish_growth(self.groups, publish=self.publish)
        self.assertEqual([p[0] for p in result[0]["packets"]], [12782, 12608])
        self.assertEqual(struct.unpack(">iihhqi", result[0]["packets"][0][1])[3], 0)
        available = self.groups.available(1134, 0)
        self.assertEqual(len(available), 1)
        self.assertEqual(available[0]["members"][0]["ref"], 5455)
        self.assertEqual(
            self.runtime.publish_growth(self.groups, publish=self.publish), []
        )
        self.assertEqual(
            Plantings(self.reopen()).mature(self.groups, publish=self.publish), []
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

    def test_world_growth_source_passes_delivery_callback_to_mature(self):
        server_root = Path(__file__).resolve().parents[1]
        source = (server_root / "local_game_server.py").read_text()
        tree = ast.parse(source)
        grow = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "grow_planted_resources"
        )
        callback = next(
            node
            for node in ast.walk(grow)
            if isinstance(node, ast.FunctionDef) and node.name == "publish_growth"
        )
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "WORLD"
                and node.func.attr == "emit_location"
                for node in ast.walk(callback)
            )
        )
        mature_call = next(
            node
            for node in ast.walk(grow)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "PLANTINGS"
            and node.func.attr == "mature"
        )
        self.assertIn(
            "publish",
            {keyword.arg for keyword in mature_call.keywords},
        )
        publish_arg = next(
            keyword.value
            for keyword in mature_call.keywords
            if keyword.arg == "publish"
        )
        self.assertIsInstance(publish_arg, ast.Name)
        self.assertEqual(publish_arg.id, "publish_growth")

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
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            2,
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
            [packet[0] for packet in last["packets"]], [13135, 12954, 12470]
        )
        self.assertEqual(
            last["packets"][2], (12470, struct.pack(">qh", item["uid"], -1))
        )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"], []
        )
        self.assertFalse(self.finish()["applied"])
        self.assertEqual(self.finish()["packets"], [])

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
