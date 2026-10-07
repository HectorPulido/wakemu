import struct
import unittest

from psycopg.errors import CheckViolation
from postgres_case import PostgresCase
from wakfu_server.harvest_inventory import grant
from wakfu_server.items.inventory_uids import allocate


class HarvestInventoryTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("harvest-items", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Harvest Items")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])

    def current_character(self, character_id=None):
        return self.store.character(
            self.account,
            self.character["id"] if character_id is None else character_id,
        )

    def grant_in_transaction(self, character, reference=4275, quantity=1):
        with self.store.connection() as db:
            return grant(db, character, reference, quantity)

    def fill_base(self, character, *, reference=12, quantity=1):
        with self.store.connection() as db:
            uid = allocate(db)
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s,0)",
                (
                    uid,
                    character["id"],
                    reference,
                    quantity,
                    character["inventory_containers"][0]["uid"],
                ),
            )
        return uid

    def shrink_base(self, character, capacity):
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_containers SET capacity=%s WHERE uid=%s",
                (capacity, character["inventory_containers"][0]["uid"]),
            )

    def test_seed_stack_reuses_uid_and_returns_quantity_delta_packet(self):
        first = self.grant_in_transaction(self.current_character(), 4275, 2)
        self.assertEqual(first["packet"][0], 12471)
        uid = first["item"]["uid"]
        second = self.grant_in_transaction(self.current_character(), 4275, 3)
        self.assertEqual(second["item"]["uid"], uid)
        self.assertEqual(second["item"]["quantity"], 5)
        self.assertEqual(second["packet"], (12470, struct.pack(">qh", uid, 3)))
        self.assertEqual(len(self.current_character()["inventory_items"]), 1)

    def test_full_pockets_without_target_stack_reject_without_changes(self):
        character = self.current_character()
        other_uid = self.fill_base(character)
        self.shrink_base(character, 1)
        before = self.current_character()["inventory_items"]
        with self.assertRaisesRegex(ValueError, "full"):
            self.grant_in_transaction(self.current_character(), 4275, 1)
        self.assertEqual(self.current_character()["inventory_items"], before)
        self.assertEqual(before[0]["uid"], other_uid)

    def test_full_pockets_still_merge_existing_seed_stack(self):
        character = self.current_character()
        first = self.grant_in_transaction(character, 4275, 2)
        self.shrink_base(self.current_character(), 1)
        second = self.grant_in_transaction(self.current_character(), 4275, 4)
        self.assertEqual(second["item"]["uid"], first["item"]["uid"])
        self.assertEqual(second["item"]["quantity"], 6)
        self.assertEqual(
            second["packet"], (12470, struct.pack(">qh", first["item"]["uid"], 4))
        )
        self.assertEqual(len(self.current_character()["inventory_items"]), 1)

    def test_stack_cap_overflow_uses_new_slot_and_full_container_rejects(self):
        character = self.current_character()
        stack = self.grant_in_transaction(character, 4275, 9998)
        self.shrink_base(self.current_character(), 2)
        split = self.grant_in_transaction(self.current_character(), 4275, 2)
        self.assertEqual(split["packet"][0], 12471)
        self.assertNotEqual(split["item"]["uid"], stack["item"]["uid"])
        self.assertEqual(split["item"]["quantity"], 2)
        self.assertEqual(split["item"]["slot"], 1)
        items = self.current_character()["inventory_items"]
        self.assertEqual([item["quantity"] for item in items], [9998, 2])

        other = self.store.create_character(self.account, "Harvest Cap")
        base = self.store.character(self.account, other["id"])
        existing = self.grant_in_transaction(base, 4275, 9998)
        self.shrink_base(base, 1)
        before = self.store.character(self.account, other["id"])["inventory_items"]
        with self.assertRaisesRegex(ValueError, "full"):
            self.grant_in_transaction(
                self.store.character(self.account, other["id"]), 4275, 2
            )
        self.assertEqual(
            self.store.character(self.account, other["id"])["inventory_items"], before
        )
        self.assertEqual(before[0]["uid"], existing["item"]["uid"])

    def test_foreign_character_stack_is_not_merged(self):
        other = self.store.create_character(self.account, "Other Harvest")
        other_stack = self.grant_in_transaction(
            self.store.character(self.account, other["id"]), 4275, 5
        )["item"]
        own = self.grant_in_transaction(self.current_character(), 4275, 2)["item"]
        self.assertNotEqual(own["uid"], other_stack["uid"])
        self.assertEqual(own["character_id"], self.character["id"])
        self.assertEqual(other_stack["character_id"], other["id"])
        self.assertEqual(
            self.store.character(self.account, other["id"])["inventory_items"][0][
                "quantity"
            ],
            5,
        )

    def test_caller_rollback_reverts_new_grant(self):
        with self.assertRaisesRegex(RuntimeError, "abort enclosing action"):
            with self.store.connection() as db:
                result = grant(db, self.current_character(), 4275, 1)
                self.assertEqual(result["packet"][0], 12471)
                raise RuntimeError("abort enclosing action")
        self.assertEqual(self.current_character()["inventory_items"], [])
        committed = self.grant_in_transaction(self.current_character(), 4275, 1)
        self.assertEqual(committed["item"]["quantity"], 1)

    def test_invalid_boolean_and_unknown_catalog_reject_before_sql(self):
        class NoSQL:
            def execute(self, *args, **kwargs):
                raise AssertionError("validation should finish before SQL")

        character = self.current_character()
        for reference, quantity in ((True, 1), (4275, True), (999999999, 1)):
            with self.subTest(reference=reference, quantity=quantity):
                with self.assertRaises(ValueError):
                    grant(NoSQL(), character, reference, quantity)

    def test_account_profession_arrays_reject_null_elements_and_multidimensional_actions(
        self,
    ):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_professions(account_id,profession_id) VALUES(%s,72)",
                (self.account,),
            )
        with self.assertRaises(CheckViolation):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE account_professions SET counters=%s WHERE account_id=%s AND profession_id=72",
                    ([1, None, 2, 3], self.account),
                )
        with self.assertRaises(CheckViolation):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE account_professions SET actions=%s WHERE account_id=%s AND profession_id=72",
                    ([100, None], self.account),
                )
        with self.assertRaises(CheckViolation):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE account_professions SET actions=%s WHERE account_id=%s AND profession_id=72",
                    ([[100, 203], [329, 310]], self.account),
                )


if __name__ == "__main__":
    unittest.main()
