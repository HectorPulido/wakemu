import struct, tempfile, unittest
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server.monster_collect import (
    Harvests,
    action,
    decode_request,
    decode_result,
    start_packet,
)
from wakfu_server.wire import proto_field


class HarvestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = [1000.0]
        self.store = Store(
            Path(self.tmp.name) / "world.sqlite3", clock=lambda: self.now[0]
        )
        self.account = self.store.register("harvest-owner", "local-password")["id"]
        self.char = self.store.create_character(self.account, "Harvest Owner")
        self.gen = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.gen, self.char["id"])
        self.harvest = Harvests(self.store)
        self.monster = dict(
            id=-4498523304664558568,
            ref=1,
            hp=10,
            map_id=self.char["map_id"],
            instance_id=self.char["instance_id"],
        )
        self.body = proto_field(8, 3723) + proto_field(
            16, self.monster["id"] % (2**64)
        )

    def tearDown(self):
        self.tmp.cleanup()

    def begin(self, **kwargs):
        return self.harvest.begin(
            self.account,
            self.gen,
            self.char["id"],
            self.body,
            self.monster,
            profession_level=0,
            reachable=True,
            quantity=1,
            **kwargs
        )

    def complete(self):
        return self.harvest.complete(
            self.account,
            self.gen,
            self.char["id"],
            b"\x02\x00\x06",
            monster=self.monster,
            profession_level=0,
        )

    def test_native_large_id_and_duration_packet(self):
        self.assertEqual(
            decode_request(self.body),
            dict(action_id=3723, monster_id=self.monster["id"]),
        )
        opcode, body = self.begin()
        self.assertEqual(opcode, 13597)
        self.assertEqual(
            struct.unpack(">Bhqqqi", body),
            (0, 6, self.char["id"], 3000, self.monster["id"], 3723),
        )

    def test_completion_grants_native_resource_once_and_survives_reconnect(self):
        self.begin()
        self.now[0] += 3.0
        result = self.complete()
        self.assertTrue(result["applied"])
        self.assertEqual(result["item"]["reference"], 2246)
        self.assertEqual(result["packets"][0][0], 12471)
        self.assertFalse(self.complete()["applied"])
        items = Store(self.store.path).character(self.account, self.char["id"])[
            "inventory_items"
        ]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["quantity"], 1)

    def test_early_finish_cancel_and_foreign_generation_do_not_grant(self):
        self.begin()
        with self.assertRaises(ValueError):
            self.complete()
        self.now[0] += 3
        with self.assertRaises(ValueError):
            self.harvest.complete(
                self.account,
                "foreign",
                self.char["id"],
                b"\x02\x00\x06",
                monster=self.monster,
                profession_level=0,
            )
        self.harvest.complete(
            self.account,
            self.gen,
            self.char["id"],
            b"\x03\x00\x06",
            monster=self.monster,
            profession_level=0,
        )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"], []
        )

    def test_expired_lease_and_target_death_reject_finish(self):
        self.begin()
        self.now[0] += 3
        self.monster["hp"] = 0
        with self.assertRaises(ValueError):
            self.complete()
        self.monster["hp"] = 10
        self.now[0] += 10000
        with self.assertRaises(ValueError):
            self.complete()

    def test_local_cooldown_transaction_and_catalog_ownership(self):
        self.begin(cooldown_seconds=10)
        self.now[0] += 3
        self.complete()
        self.begin(cooldown_seconds=10)
        self.now[0] += 3
        with self.assertRaises(ValueError):
            self.complete()
        self.assertEqual(
            len(self.store.character(self.account, self.char["id"])["inventory_items"]),
            1,
        )
        with self.assertRaises(ValueError):
            action(1740, 3723)
        with self.assertRaises(ValueError):
            decode_result(b"\x02\x00\x08")

    def test_inventory_full_and_position_change_leave_no_partial_receipt(self):
        self.begin()
        self.now[0] += 3
        with self.store.connection() as db:
            db.execute("UPDATE characters SET x=x+1 WHERE id=?", (self.char["id"],))
        with self.assertRaises(ValueError):
            self.complete()
        with self.store.connection() as db:
            db.execute("UPDATE characters SET x=x-1 WHERE id=?", (self.char["id"],))
            base = self.char["inventory_containers"][0]
            for slot in range(base["capacity"]):
                db.execute(
                    "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) VALUES(?,?,?,?,?,?)",
                    (2**40 + slot, self.char["id"], 2021, 1, base["uid"], slot),
                )
        with self.assertRaises(ValueError):
            self.complete()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM monster_harvest_receipts").fetchone()[
                    0
                ],
                0,
            )

    def test_native_stack_limit_rejects_before_occupation(self):
        from wakfu_server.inventory_move import STACKS

        with self.assertRaises(ValueError):
            self.harvest.begin(
                self.account,
                self.gen,
                self.char["id"],
                self.body,
                self.monster,
                profession_level=0,
                reachable=True,
                quantity=STACKS[2246]["maximum"] + 1,
            )
        self.assertEqual(self.harvest.pending, {})

    def test_stale_session_cleanup_preserves_new_generation_occupation(self):
        self.begin()
        oldgen = self.gen
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET expires_at=0 WHERE account_id=?", (self.account,)
            )
        self.gen = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.gen, self.char["id"])
        self.begin()
        self.assertFalse(self.harvest.cancel(self.char["id"], oldgen))
        self.assertEqual(self.harvest.pending[self.char["id"]]["generation"], self.gen)
        self.now[0] += 3
        self.assertTrue(self.complete()["applied"])

    def test_generation_scoped_cancel_matches_only_current_owner(self):
        self.begin()
        self.assertFalse(self.harvest.cancel(self.char["id"], "unrelated"))
        self.assertTrue(self.harvest.cancel(self.char["id"], self.gen))
        self.assertEqual(self.harvest.pending, {})
