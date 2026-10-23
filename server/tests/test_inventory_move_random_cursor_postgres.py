"""Public12804 preserves UID-bound random-use cursors across physical moves."""
import struct

from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_move import transfer
from wakfu_server.inventory_uids import reserve


class InventoryMoveRandomCursorPostgresTests(PostgresCase):
    def test_split_replay_full_move_and_merge_refusal_preserve_cursors(self):
        account = self.store.register("cursor-move-owner", "local-password")["id"]
        character = self.store.create_character(account, "Cursor Move Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        bag = character["inventory_containers"][0]["uid"]
        source = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=12408,
            quantity=5,
            container=bag,
            slot=0,
            allowed_references={12408},
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO random_item_use_counters(source_uid,next_use) VALUES(%s,7)",
                (source["uid"],),
            )
        clone = reserve(self.store, account, generation, character["id"], count=1)[
            "uids"
        ][0]
        split_body = struct.pack(">qqqhBqh", source["uid"], bag, bag, 1, 1, clone, 2)
        split = transfer(self.store, account, generation, character["id"], split_body)
        self.assertTrue(split["applied"])
        self.assertEqual(
            {source["uid"]: 3, clone: 2},
            {
                row["uid"]: row["quantity"]
                for row in split["character"]["inventory_items"]
            },
        )

        def state():
            with self.store.connection() as db:
                items = [
                    dict(row)
                    for row in db.execute(
                        "SELECT uid,quantity,container,slot FROM inventory_items WHERE character_id=%s ORDER BY uid",
                        (character["id"],),
                    )
                ]
                cursors = [
                    dict(row)
                    for row in db.execute(
                        "SELECT source_uid,next_use FROM random_item_use_counters "
                        "WHERE source_uid IN (SELECT uid FROM inventory_items WHERE character_id=%s) ORDER BY source_uid",
                        (character["id"],),
                    )
                ]
            return items, cursors

        before = state()
        self.assertEqual(
            {source["uid"]: 7, clone: 7},
            {row["source_uid"]: row["next_use"] for row in before[1]},
        )
        self.assertFalse(
            transfer(self.store, account, generation, character["id"], split_body)[
                "applied"
            ]
        )
        self.assertEqual(before, state())
        moved = transfer(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qqqhB", clone, bag, bag, 5, 0),
        )
        self.assertTrue(moved["applied"])
        self.assertEqual(
            5,
            next(
                row["slot"]
                for row in moved["character"]["inventory_items"]
                if row["uid"] == clone
            ),
        )
        self.assertEqual(before[1], state()[1])
        self.assertFalse(
            transfer(self.store, account, generation, character["id"], split_body)[
                "applied"
            ]
        )
        self.assertEqual(
            5, next(row["slot"] for row in state()[0] if row["uid"] == clone)
        )

        plain = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=12408,
            quantity=1,
            container=bag,
            slot=2,
            allowed_references={12408},
        )
        # Equal cursors still represent different UID-bound random streams;
        # either one-sided cursor must also prevent destroying that identity.
        for uid, target in ((clone, 0), (plain["uid"], 0), (clone, 2)):
            before = state()
            with self.subTest(uid=uid, target=target), self.assertRaisesRegex(
                ValueError, "cannot be merged"
            ):
                transfer(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    struct.pack(">qqqhB", uid, bag, bag, target, 0),
                )
            self.assertEqual(before, state())
        self.assertEqual(6, sum(row["quantity"] for row in state()[0]))
        self.assertEqual(
            {source["uid"]: 7, clone: 7},
            {row["source_uid"]: row["next_use"] for row in state()[1]},
        )
