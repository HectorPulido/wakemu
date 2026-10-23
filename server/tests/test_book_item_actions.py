"""Reusable native book authorization, inventory custody and exact wire grammar."""
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import book_item_actions
from wakfu_server.characters import heroes
from wakfu_server.inventory_items import grant
from wakfu_server.haven_bag_furniture_knowledge import _rules


class BookItemActionGrammarTests(unittest.TestCase):
    def test_book_grammar_keeps_unknown_families_and_rejects_suffix_or_bad_identity(
        self,
    ):
        with patch.object(
            book_item_actions,
            "_action_classes",
            return_value={
                12: {"bHU"},
                13: {"bIi"},
                14: {"bHU", "bIt"},
            },
        ):
            self.assertEqual(
                book_item_actions.action_class(struct.pack(">iq", 12, 123)), "bHU"
            )
            self.assertIsNone(
                book_item_actions.action_class(struct.pack(">iq", 13, 123))
            )
            for body in (
                b"",
                struct.pack(">iq", 12, 0),
                struct.pack(">iq", 14, 123),
                struct.pack(">iq", 12, 123) + b"\x00",
            ):
                with self.subTest(body=body), self.assertRaises(ValueError):
                    book_item_actions.action_class(body)


class BookItemActionPostgresTests(PostgresCase):
    def fixture(self, username="book-reader"):
        account = self.store.register(username, "local-password")["id"]
        main = self.store.create_character(
            account, "Book Reader" if username == "book-reader" else "Other Book Reader"
        )
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        return account, generation, main

    def give(self, account, generation, character, reference, slot=0):
        current = self.store.character(account, character["id"])
        container = next(
            row for row in current["inventory_containers"] if row["kind"] == 0
        )
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=reference,
            quantity=2,
            container=container["uid"],
            slot=slot,
            allowed_references={reference},
        )

    def body(self, reference, uid):
        return struct.pack(">iq", _rules()[reference]["use_action_id"], uid)

    def test_all_160_books_are_reusable_and_repeated_hero_reads_preserve_inventory(
        self,
    ):
        account, generation, main = self.fixture()
        hero = self.store.create_character(account, "Book Hero")
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        item = self.give(account, generation, hero, 8053)
        body = self.body(8053, item["uid"])
        with self.store.connection() as db:
            descriptors = list(db.execute("SELECT * FROM native_book_item_actions"))
        self.assertEqual(len(descriptors), 160)
        self.assertTrue(all(row["consumes_source"] is False for row in descriptors))
        self.assertTrue(
            all(
                row["source_sha256"] == book_item_actions.SOURCE_SHA256
                for row in descriptors
            )
        )
        for _ in range(2):
            result = book_item_actions.use(
                self.store, account, generation, main["id"], body, in_fight=False
            )
            self.assertEqual(result["character"]["id"], hero["id"])
            self.assertEqual(
                (
                    result["validated"],
                    result["applied"],
                    result["consumed"],
                    result["background_id"],
                ),
                (True, False, 0, 35),
            )
            self.assertEqual(result["packets"], [])
            self.assertEqual(
                result["native_parameters"], ["35", '"AnimEmote-Lire-Debut"']
            )
        restored = self.reopen().character(account, hero["id"])
        physical = next(
            row for row in restored["inventory_items"] if row["uid"] == item["uid"]
        )
        self.assertEqual((physical["reference"], physical["quantity"]), (8053, 2))
        with self.store.connection() as db:
            selected = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s", (account,)
            ).fetchone()
        self.assertEqual(selected["character_id"], main["id"])

    def test_foreign_wrong_action_combat_stale_lease_and_bad_authority_do_not_consume(
        self,
    ):
        account, generation, main = self.fixture()
        item = self.give(account, generation, main, 8053)
        body = self.body(8053, item["uid"])
        other, other_generation, other_main = self.fixture("other-book-reader")
        requests = [
            (other, other_generation, other_main["id"], body, False),
            (account, generation, main["id"], self.body(8071, item["uid"]), False),
            (account, generation, main["id"], body, True),
            (account, "expired-book-lease", main["id"], body, False),
        ]
        for owner, lease, character_id, request, combat in requests:
            with self.subTest(
                owner=owner, lease=lease, combat=combat
            ), self.assertRaises(ValueError):
                book_item_actions.use(
                    self.store, owner, lease, character_id, request, in_fight=combat
                )
        with self.store.connection() as db:
            db.execute(
                "UPDATE native_book_item_actions SET source_sha256=%s WHERE item_ref=8053",
                ("0" * 64,),
            )
        with self.assertRaises(ValueError):
            book_item_actions.use(
                self.store, account, generation, main["id"], body, in_fight=False
            )
        current = self.store.character(account, main["id"])
        physical = next(
            row for row in current["inventory_items"] if row["uid"] == item["uid"]
        )
        self.assertEqual(physical["quantity"], 2)
