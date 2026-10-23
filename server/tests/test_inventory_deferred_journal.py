import struct
import unittest
from unittest.mock import MagicMock, Mock, patch

from postgres_case import PostgresCase
from wakfu_server.inventory_deferred_journal import query
from wakfu_server.characters import heroes


class InventoryJournalGrammarTests(unittest.TestCase):
    def test_malformed_query_never_opens_database_but_valid_query_needs_no_baseline_marker(
        self,
    ):
        store = Mock()
        for body in (
            b"",
            b"\x00" * 7,
            b"\x00" * 9,
            struct.pack(">q", 0),
            struct.pack(">q", -1),
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                query(store, 1, "generation", body)
        store.connection.assert_not_called()

        store = MagicMock()
        with patch(
            "wakfu_server.inventory_deferred_journal.lock_inventory_character"
        ) as lock:
            self.assertEqual(
                query(store, 1, "generation", struct.pack(">q", 7)), (12852, b"\x00")
            )
        db = store.connection.return_value.__enter__.return_value
        lock.assert_called_once_with(store, db, 1, "generation", 7)


class InventoryJournalPostgresTests(PostgresCase):
    def test_selected_main_and_active_hero_share_real_lease_without_baseline_gate_or_mutation(
        self,
    ):
        account = self.store.register("journal-owner", "local-password")["id"]
        main = self.store.create_character(account, "Journal Main")
        hero = self.store.create_character(account, "Journal Hero")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        before = self.store.character(account, main["id"])
        for identity in sorted((main["id"], hero["id"])):
            with self.subTest(identity=identity):
                self.assertEqual(
                    query(
                        self.store,
                        account,
                        generation,
                        struct.pack(">q", identity),
                    ),
                    (12852, b"\x00"),
                )
        after = self.store.character(account, main["id"])
        for key in (
            "inventory_items",
            "inventory_containers",
            "builds",
            "map_id",
            "instance_id",
            "x",
            "y",
            "z",
            "hp",
            "max_hp",
        ):
            self.assertEqual(after[key], before[key], key)

    def test_stale_foreign_and_inactive_owned_actor_are_rejected(self):
        account = self.store.register("journal-fenced", "local-password")["id"]
        main = self.store.create_character(account, "Journal Fenced")
        inactive = self.store.create_character(account, "Journal Inactive")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        other = self.store.register("journal-foreign", "local-password")["id"]
        foreign = self.store.create_character(other, "Journal Foreign")
        for identity, lease in (
            (main["id"], "stale"),
            (inactive["id"], generation),
            (foreign["id"], generation),
        ):
            with self.subTest(identity=identity, lease=lease), self.assertRaises(
                ValueError
            ):
                query(self.store, account, lease, struct.pack(">q", identity))
