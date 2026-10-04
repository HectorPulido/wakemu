import struct, tempfile, unittest
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server.planting_runtime import Plantings
from wakfu_server.planting import SEEDS
from wakfu_server.inventory_items import grant
from wakfu_server.profession_store import ensure_learned
from wakfu_server.combat_groups import Groups


class RuntimePlantingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = [1000.0]
        self.store = Store(
            Path(self.tmp.name) / "world.sqlite3", clock=lambda: self.now[0]
        )
        self.account = self.store.register("runtime-planter", "local-password")["id"]
        self.char = self.store.create_character(self.account, "Runtime Planter")
        self.gen = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.gen, self.char["id"])
        self.runtime = Plantings(self.store)
        self.groups = Groups()

    def tearDown(self):
        self.tmp.cleanup()

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
        self.assertEqual([p[0] for p in result["packets"]], [13135, 12954])
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
        result = self.runtime.mature(self.groups)
        self.assertEqual([p[0] for p in result[0]["packets"]], [12782])
        self.assertEqual(struct.unpack(">iihhqi", result[0]["packets"][0][1])[3], 2)
        self.assertEqual(self.runtime.mature(self.groups), [])

    def test_seed_monster_growth_and_redis_retry_are_idempotent(self):
        self.begin(self.seed(30927))
        self.now[0] += 3
        self.finish()
        self.now[0] += 30

        class Broken:
            def register(self, *args):
                raise ConnectionError("Redis unavailable")

        with self.assertRaises(ConnectionError):
            self.runtime.mature(Broken())
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
        result = self.runtime.publish_growth(self.groups)
        self.assertEqual([p[0] for p in result[0]["packets"]], [12782, 12608])
        self.assertEqual(struct.unpack(">iihhqi", result[0]["packets"][0][1])[3], 0)
        available = self.groups.available(1134, 0)
        self.assertEqual(len(available), 1)
        self.assertEqual(available[0]["members"][0]["ref"], 5455)
        self.assertEqual(self.runtime.publish_growth(self.groups), [])
        self.assertEqual(Plantings(Store(self.store.path)).mature(self.groups), [])

    def test_generation_fencing_cancel_and_takeover(self):
        body = self.seed(4275)
        self.begin(body)
        old = self.gen
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET expires_at=0 WHERE account_id=?", (self.account,)
            )
        self.gen = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.gen, self.char["id"])
        self.begin(body)
        self.assertFalse(self.runtime.cancel(self.char["id"], old))
        self.now[0] += 3
        self.assertTrue(self.finish()["applied"])

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

    def test_spawn_occupation_blocks_and_movement_rejects_without_consumption(self):
        body = self.seed(4275)
        self.begin(body)
        with self.assertRaises(ValueError):
            self.begin(body)
        self.now[0] += 3
        with self.store.connection() as db:
            db.execute("UPDATE characters SET x=x+1 WHERE id=?", (self.char["id"],))
        with self.assertRaises(ValueError):
            self.finish()
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            2,
        )
