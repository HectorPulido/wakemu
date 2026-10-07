import struct
import unittest
import uuid

from postgres_case import PostgresCase

from wakfu_server import temporary_recycling
from wakfu_server.inventory_move import STACKS


class TemporaryRecyclingTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.owner = self._player("temp-recycler")

    def _player(self, username):
        account = self.store.register(
            username + uuid.uuid4().hex[:8], "temporary-recycle-password"
        )["id"]
        suffix = (
            uuid.uuid4()
            .hex[:8]
            .translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
        )
        character = self.store.create_character(account, "TempRecycle" + suffix)
        generation = self.store.begin_session(account, ttl=10000)
        character = self.store.select_character(account, generation, character["id"])
        return dict(account=account, generation=generation, character=character)

    def _temporary_item(self, owner, reference=2021, quantity=1, *, bound=False):
        character_id = owner["character"]["id"]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (fight_id, character_id, owner["account"]),
            )
            db.execute(
                "INSERT INTO fight_drop_awards(fight_id,character_id,account_id,generation,"
                "policy_version,snapshot,snapshot_sha256) VALUES(%s,%s,%s,%s,1,'{}',%s)",
                (
                    fight_id,
                    character_id,
                    owner["account"],
                    owner["generation"],
                    "0" * 64,
                ),
            )
            db.execute(
                "INSERT INTO fight_drop_attempt_receipts(fight_id,character_id,defeated_actor_id,"
                "monster_reference,drop_row_index,attempt_index,item_reference,success,quantity,"
                "quantity_min,quantity_max,base_probability,raw_probability,effective_probability,"
                "draw_numerator,quantity_draw_numerator,roll_count,native_roll_max,native_min_prospection) "
                "VALUES(%s,%s,-9001,1,0,0,%s,true,%s,%s,%s,1,1,1,0,0,1,100,0)",
                (fight_id, character_id, reference, quantity, quantity, quantity),
            )
            db.execute(
                "INSERT INTO fight_drop_delivery_receipts(fight_id,character_id,defeated_actor_id,"
                "drop_row_index,attempt_index,item_reference,awarded_quantity,inventory_quantity,"
                "temporary_quantity) VALUES(%s,%s,-9001,0,0,%s,%s,0,%s)",
                (fight_id, character_id, reference, quantity, quantity),
            )
            return db.execute(
                "INSERT INTO temporary_combat_items(character_id,reference,quantity,bound,fight_id,"
                "defeated_actor_id,drop_row_index,attempt_index) VALUES(%s,%s,%s,%s,%s,-9001,0,0) "
                "RETURNING uid",
                (character_id, reference, quantity, bound, fight_id),
            ).fetchone()["uid"]

    def _request(self, owner, *uids, rng=None, generation=None, character_id=None):
        _, body = temporary_recycling.request(
            owner["character"]["id"] if character_id is None else character_id,
            list(uids),
        )
        return temporary_recycling.recycle(
            self.store,
            owner["account"],
            owner["generation"] if generation is None else generation,
            owner["character"]["id"],
            body,
            rng=rng,
        )

    def fetchone(self, sql, params=()):
        with self.store.connection() as db:
            return db.execute(sql, params).fetchone()

    def test_native_13447_layout_and_malformed_requests(self):
        opcode, body = temporary_recycling.request(0x102030405, [7, 9])
        self.assertEqual(13447, opcode)
        self.assertEqual(
            bytes.fromhex("0000000102030405000200000000000000070000000000000009"), body
        )
        self.assertEqual(
            {"character_id": 0x102030405, "uids": [7, 9]},
            temporary_recycling.decode_request(13447, body),
        )
        for bad_opcode, bad_body in (
            (12787, body),
            (13447, body[:-1]),
            (13447, body + b"\x00"),
            (13447, struct.pack(">qh", 1, 0)),
            (13447, struct.pack(">qhq", 1, 1, 0)),
            (13447, struct.pack(">qhqq", 1, 2, 7, 7)),
            (13447, struct.pack(">qhq", 0, 1, 7)),
        ):
            with self.subTest(bad_opcode=bad_opcode, body=bad_body), self.assertRaises(
                ValueError
            ):
                temporary_recycling.decode_request(bad_opcode, bad_body)
        for character_id, uids in (
            (True, [1]),
            (0, [1]),
            (1, []),
            (1, [0]),
            (1, [1, 1]),
        ):
            with self.subTest(character_id=character_id, uids=uids), self.assertRaises(
                ValueError
            ):
                temporary_recycling.request(character_id, uids)

    def test_temporary_2021_zero_yield_consumes_with_native_snapshots_and_replay(self):
        uid = self._temporary_item(self.owner)
        calls = []
        result = self._request(self.owner, uid, rng=lambda: calls.append(0.03) or 0.03)
        self.assertTrue(result["applied"])
        self.assertEqual([0.03], calls)
        self.assertEqual({"27083": 0}, result["receipt"]["products"])
        self.assertEqual(
            [(13713, None), (13078, None), (12691, None), (12890, None)],
            [(opcode, None) for opcode, _ in result["packets"]],
        )
        self.assertEqual(struct.pack(">ii", 0, 1), result["packets"][-1][1])
        self.assertEqual(
            struct.pack(">qB", self.owner["character"]["id"], 3),
            result["packets"][2][1],
        )
        self.assertIsNone(
            self.fetchone("SELECT uid FROM temporary_combat_items WHERE uid=%s", (uid,))
        )
        replay = self._request(
            self.owner, uid, rng=lambda: self.fail("replay drew again")
        )
        self.assertFalse(replay["applied"])
        self.assertEqual(struct.pack(">ii", 0, 1), replay["packets"][-1][1])
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT count(*) AS n FROM temporary_item_recycling_receipts WHERE character_id=%s",
                (self.owner["character"]["id"],),
            )["n"],
        )

    def test_quantity_preview_count_uses_stack_quantity_and_products_merge(self):
        first = self._temporary_item(self.owner, quantity=25)
        second = self._temporary_item(self.owner, quantity=25)
        calls = []
        result = self._request(
            self.owner, first, second, rng=lambda: calls.append(0.99) or 0.99
        )
        self.assertEqual(50, result["receipt"]["destroyed_items"])
        self.assertEqual(struct.pack(">ii", 1, 50), result["packets"][-1][1])
        product = self.fetchone(
            "SELECT reference,quantity FROM inventory_items WHERE character_id=%s AND reference=27083",
            (self.owner["character"]["id"],),
        )
        self.assertEqual((27083, 1), (product["reference"], product["quantity"]))
        self.assertEqual(1, len(calls))

    def test_durable_active_fight_rejects_without_consumption(self):
        uid = self._temporary_item(self.owner)
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (fight_id, self.owner["character"]["id"], self.owner["account"]),
            )
        with self.assertRaisesRegex(ValueError, "during combat"):
            self._request(self.owner, uid, rng=lambda: 0.0)
        self.assertIsNotNone(
            self.fetchone("SELECT uid FROM temporary_combat_items WHERE uid=%s", (uid,))
        )

    def test_non_shard_foreign_and_wrong_session_requests_leave_source_untouched(self):
        powder = self._temporary_item(self.owner, reference=1718)
        with self.assertRaisesRegex(ValueError, "not eligible"):
            self._request(self.owner, powder, rng=lambda: 0.0)
        self.assertIsNotNone(
            self.fetchone(
                "SELECT uid FROM temporary_combat_items WHERE uid=%s", (powder,)
            )
        )

        other = self._player("temp-other")
        foreign_uid = self._temporary_item(other)
        with self.assertRaisesRegex(ValueError, "foreign or missing"):
            self._request(self.owner, foreign_uid, rng=lambda: 0.0)
        with self.assertRaisesRegex(ValueError, "Invalid inventory session"):
            self._request(
                self.owner,
                self._temporary_item(self.owner),
                generation="stale",
                rng=lambda: 0.0,
            )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM temporary_item_recycling_receipts WHERE character_id=%s",
                (self.owner["character"]["id"],),
            )["n"],
        )

    def test_full_inventory_rolls_back_source_receipt_and_product_grant(self):
        uid = self._temporary_item(self.owner, quantity=50)
        base = self.fetchone(
            "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s AND kind=0",
            (self.owner["character"]["id"],),
        )
        max_stack = STACKS[27083]["maximum"]
        with self.store.connection() as db:
            for slot in range(base["capacity"]):
                db.execute(
                    "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                    "VALUES(%s,27083,%s,%s,%s)",
                    (self.owner["character"]["id"], max_stack, base["uid"], slot),
                )
        with self.assertRaisesRegex(ValueError, "Base inventory full"):
            self._request(self.owner, uid, rng=lambda: 0.99)
        self.assertIsNotNone(
            self.fetchone("SELECT uid FROM temporary_combat_items WHERE uid=%s", (uid,))
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM temporary_item_recycling_receipts WHERE character_id=%s",
                (self.owner["character"]["id"],),
            )["n"],
        )
        self.assertEqual(
            base["capacity"],
            self.fetchone(
                "SELECT count(*) AS n FROM inventory_items WHERE container=%s",
                (base["uid"],),
            )["n"],
        )

    def test_receipt_failure_rolls_back_temp_delete_and_products(self):
        uid = self._temporary_item(self.owner, quantity=50)
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_temp_recycle_receipt() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'injected temporary recycling receipt failure'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_temp_recycle_receipt BEFORE INSERT ON "
                "temporary_item_recycling_receipts FOR EACH ROW EXECUTE FUNCTION reject_temp_recycle_receipt()"
            )
        with self.assertRaisesRegex(
            Exception, "injected temporary recycling receipt failure"
        ):
            self._request(self.owner, uid, rng=lambda: 0.99)
        self.assertIsNotNone(
            self.fetchone("SELECT uid FROM temporary_combat_items WHERE uid=%s", (uid,))
        )
        self.assertIsNone(
            self.fetchone(
                "SELECT uid FROM inventory_items WHERE character_id=%s AND reference=27083",
                (self.owner["character"]["id"],),
            )
        )
        with self.store.connection() as db:
            db.execute(
                "DROP TRIGGER reject_temp_recycle_receipt ON temporary_item_recycling_receipts"
            )
            db.execute("DROP FUNCTION reject_temp_recycle_receipt()")
        retry = self._request(self.owner, uid, rng=lambda: 0.99)
        self.assertTrue(retry["applied"])
