import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from postgres_case import PostgresCase


class SocialContactsTests(PostgresCase):
    def setUp(self):
        super().setUp()
        from wakfu_server.social_contacts import SocialContacts

        self.clock = [1_700_000_000.0]
        self.store.clock = lambda: self.clock[0]
        suffix = uuid.uuid4().hex[:10]
        self.owner = self.store.register("social_owner_" + suffix, "test-password")
        self.peer = self.store.register("social_peer_" + suffix, "test-password")
        self.other = self.store.register("social_other_" + suffix, "test-password")
        self.owner_generation = self.store.begin_session(self.owner["id"])
        self.peer_generation = self.store.begin_session(self.peer["id"])
        self.owner_character = self.store.create_character(
            self.owner["id"], "Social Owner"
        )
        self.peer_character = self.store.create_character(
            self.peer["id"], "Social Peer"
        )
        self.store.select_character(
            self.peer["id"], self.peer_generation, self.peer_character["id"]
        )
        self.contacts = SocialContacts(self.store)

    def test_add_lookup_casefold_bootstrap_online_data_and_durable_reopen(self):
        from wakfu_server.social_wire import decode_friend_lists

        with self.store.connection() as db:
            db.execute(
                "UPDATE character_progression SET xp=4567 WHERE character_id=%s",
                (self.peer_character["id"],),
            )

        added = self.contacts.add_friend(
            self.owner["id"], self.owner_generation, self.peer_character["name"].upper()
        )
        self.assertEqual(self.peer["id"], added["account_id"])
        self.assertEqual(
            {
                "character_name": self.peer_character["name"],
                "breed_id": self.peer_character["breed"],
                "sex": int(self.peer_character["sex"]),
                "xp": 4567,
            },
            {key: added[key] for key in ("character_name", "breed_id", "sex", "xp")},
        )
        self.assertTrue(added["changed"])
        self.assertFalse(
            self.contacts.add_friend(
                self.owner["id"], self.owner_generation, self.peer_character["name"]
            )["changed"]
        )
        snapshot = self.contacts.snapshot(self.owner["id"], self.owner_generation)
        self.assertEqual(
            [
                {
                    "account_id": self.peer["id"],
                    "account_name": self.peer["username"],
                    "is_online": True,
                    "character_name": self.peer_character["name"],
                    "breed_id": self.peer_character["breed"],
                    "sex": int(self.peer_character["sex"]),
                    "xp": 4567,
                }
            ],
            snapshot["friends"],
        )
        self.assertEqual([], snapshot["ignored"])
        self.assertEqual(
            snapshot["friends"],
            self.contacts.snapshot(self.owner["id"], self.owner_generation)["friends"],
        )
        self.assertEqual(
            {"friends": snapshot["friends"], "ignored": []},
            decode_friend_lists(
                self.contacts.bootstrap_payload(self.owner["id"], self.owner_generation)
            ),
        )
        reopened = self.reopen()
        reopened.clock = lambda: self.clock[0]
        from wakfu_server.social_contacts import SocialContacts

        self.assertEqual(
            [self.peer["id"]],
            [
                entry["account_id"]
                for entry in SocialContacts(reopened).snapshot(
                    self.owner["id"], self.owner_generation
                )["friends"]
            ],
        )

    def test_ignore_and_friend_are_mutually_exclusive_and_self_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "own account"):
            self.contacts.add_ignore(
                self.owner["id"], self.owner_generation, self.owner_character["name"]
            )
        self.contacts.add_friend(
            self.owner["id"], self.owner_generation, self.peer_character["name"]
        )
        with self.assertRaisesRegex(ValueError, "other contact relation"):
            self.contacts.add_ignore(
                self.owner["id"], self.owner_generation, self.peer_character["name"]
            )
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM account_social_contacts WHERE owner_account_id=%s",
                    (self.owner["id"],),
                ).fetchone()["n"],
            )

    def test_remove_is_owner_scoped_and_only_removes_requested_relation(self):
        self.contacts.add_ignore(
            self.owner["id"], self.owner_generation, self.peer_character["name"]
        )
        self.contacts.add_friend(
            self.other["id"],
            self.store.begin_session(self.other["id"]),
            self.peer_character["name"],
        )
        self.assertFalse(
            self.contacts.remove_friend(
                self.owner["id"], self.owner_generation, self.peer["id"]
            )
        )
        self.assertTrue(
            self.contacts.remove_ignore(
                self.owner["id"], self.owner_generation, self.peer["id"]
            )
        )
        self.assertFalse(
            self.contacts.remove_ignore(
                self.owner["id"], self.owner_generation, self.peer["id"]
            )
        )
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM account_social_contacts WHERE owner_account_id=%s AND contact_account_id=%s",
                    (self.other["id"], self.peer["id"]),
                ).fetchone()["n"],
            )

    def test_stale_replaced_and_expired_generation_cannot_mutate(self):
        old_generation = self.owner_generation
        self.owner_generation = self.store.begin_session(self.owner["id"])
        for generation in (old_generation, "foreign-generation"):
            with self.subTest(generation=generation), self.assertRaisesRegex(
                ValueError, "stale or expired"
            ):
                self.contacts.add_friend(
                    self.owner["id"], generation, self.peer_character["name"]
                )
        self.clock[0] += 61
        with self.assertRaisesRegex(ValueError, "stale or expired"):
            self.contacts.add_ignore(
                self.owner["id"], self.owner_generation, self.peer_character["name"]
            )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM account_social_contacts"
                ).fetchone()["n"],
            )

    def test_dnd_empty_request_semantics_are_durable_toggle_and_711_boolean(self):
        self.assertFalse(self.contacts.do_not_disturb(self.owner["id"]))
        self.assertTrue(
            self.contacts.toggle_do_not_disturb(self.owner["id"], self.owner_generation)
        )
        reopened = self.reopen()
        reopened.clock = lambda: self.clock[0]
        from wakfu_server.social_contacts import SocialContacts

        reopened_contacts = SocialContacts(reopened)
        self.assertTrue(reopened_contacts.do_not_disturb(self.owner["id"]))
        self.assertFalse(
            reopened_contacts.toggle_do_not_disturb(
                self.owner["id"], self.owner_generation
            )
        )
        self.assertFalse(
            reopened_contacts.snapshot(self.owner["id"], self.owner_generation)[
                "do_not_disturb"
            ]
        )

    def test_private_chat_block_reason_is_recipient_owned_and_dnd_precedes_ignore(self):
        self.assertIsNone(
            self.contacts.private_chat_block_reason(self.owner["id"], self.peer["id"])
        )
        self.contacts.add_ignore(
            self.peer["id"], self.peer_generation, self.owner_character["name"]
        )
        self.assertEqual(
            103,
            self.contacts.private_chat_block_reason(self.owner["id"], self.peer["id"]),
        )
        self.assertIsNone(
            self.contacts.private_chat_block_reason(self.peer["id"], self.owner["id"])
        )
        self.contacts.toggle_do_not_disturb(self.peer["id"], self.peer_generation)
        self.assertEqual(
            102,
            self.contacts.private_chat_block_reason(self.owner["id"], self.peer["id"]),
        )

    def test_concurrent_duplicate_add_has_one_durable_contact(self):
        barrier = threading.Barrier(2)

        def add(_):
            barrier.wait(timeout=5)
            return self.contacts.add_friend(
                self.owner["id"], self.owner_generation, self.peer_character["name"]
            )["changed"]

        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual([False, True], sorted(workers.map(add, range(2))))
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM account_social_contacts WHERE owner_account_id=%s AND contact_account_id=%s",
                    (self.owner["id"], self.peer["id"]),
                ).fetchone()["n"],
            )

    def test_database_rejects_self_and_duplicate_relationship_rows(self):
        from psycopg.errors import CheckViolation, UniqueViolation

        with self.assertRaises(CheckViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO account_social_contacts(owner_account_id,contact_account_id,relation) "
                    "VALUES(%s,%s,'friend')",
                    (self.owner["id"], self.owner["id"]),
                )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_social_contacts(owner_account_id,contact_account_id,relation) "
                "VALUES(%s,%s,'friend')",
                (self.owner["id"], self.peer["id"]),
            )
        with self.assertRaises(UniqueViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO account_social_contacts(owner_account_id,contact_account_id,relation) "
                    "VALUES(%s,%s,'ignore')",
                    (self.owner["id"], self.peer["id"]),
                )

    def test_native_input_resolves_character_name_and_does_not_guess_username_match(
        self,
    ):
        offline = self.store.register("SocialOffline", "test-password")
        self.store.begin_session(offline["id"])
        with self.assertRaisesRegex(ValueError, "character not found"):
            self.contacts.add_friend(
                self.owner["id"], self.owner_generation, offline["username"]
            )
        with self.assertRaisesRegex(ValueError, "character not found"):
            self.contacts.add_ignore(
                self.owner["id"], self.owner_generation, "Missing Character"
            )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM account_social_contacts WHERE owner_account_id=%s",
                    (self.owner["id"],),
                ).fetchone()["n"],
            )

    def test_native_dispatch_acks_use_resolved_character_and_removal_account_id(self):
        import struct

        from wakfu_server.social_dispatch import SocialDispatcher
        from wakfu_server.social_wire import (
            decode_add_friend_ack,
            decode_add_ignore_ack,
            decode_do_not_disturb_status,
            decode_friend_lists,
            decode_remove_friend_ack,
            decode_remove_ignore_ack,
        )

        dispatcher = SocialDispatcher(self.contacts)
        name = self.peer_character["name"].encode("utf-8")
        friend_opcode, friend_body = dispatcher.handle(
            784, bytes((len(name),)) + name, self.owner["id"], self.owner_generation
        )
        self.assertEqual(718, friend_opcode)
        self.assertEqual(
            {
                "account_id": self.peer["id"],
                "account_name": self.peer["username"],
                "character_name": self.peer_character["name"],
                "breed_id": self.peer_character["breed"],
                "sex": int(self.peer_character["sex"]),
                "xp": 0,
            },
            decode_add_friend_ack(friend_body),
        )
        bootstrap = dispatcher.bootstrap(self.owner["id"], self.owner_generation)
        self.assertEqual([630, 711], [packet[0] for packet in bootstrap])
        self.assertEqual(
            [self.peer["id"]],
            [c["account_id"] for c in decode_friend_lists(bootstrap[0][1])["friends"]],
        )
        self.assertFalse(decode_do_not_disturb_status(bootstrap[1][1]))

        removed_friend = dispatcher.handle(
            672,
            struct.pack(">q", self.peer["id"]),
            self.owner["id"],
            self.owner_generation,
        )
        self.assertEqual(
            (719, {"account_id": self.peer["id"]}),
            (removed_friend[0], decode_remove_friend_ack(removed_friend[1])),
        )
        ignore_opcode, ignore_body = dispatcher.handle(
            657, bytes((len(name),)) + name, self.owner["id"], self.owner_generation
        )
        self.assertEqual(641, ignore_opcode)
        self.assertEqual(
            {
                "account_id": self.peer["id"],
                "account_name": self.peer["username"],
                "character_name": self.peer_character["name"],
            },
            decode_add_ignore_ack(ignore_body),
        )
        removed_ignore = dispatcher.handle(
            799,
            struct.pack(">q", self.peer["id"]),
            self.owner["id"],
            self.owner_generation,
        )
        self.assertEqual(
            {"account_id": self.peer["id"], "account_name": self.peer["username"]},
            decode_remove_ignore_ack(removed_ignore[1]),
        )
        dnd = dispatcher.handle(12449, b"", self.owner["id"], self.owner_generation)
        self.assertEqual((711, b"\x01"), dnd)
        self.assertEqual(
            b"", dispatcher.bootstrap(self.owner["id"], self.owner_generation)[0][1]
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
