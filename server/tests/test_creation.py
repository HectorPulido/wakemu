import struct
import unittest
from postgres_case import PostgresCase
from wakfu_server.creation import create, select_created
from wakfu_server.characters import heroes
from wakfu_server.wire import appearance_section


class CreationTests(PostgresCase):
    def test_creation_auto_selection_rebinds_existing_company_before_world_join(self):
        store = self.store
        account = store.register("creator-company", "creation-password")["id"]
        previous = store.create_character(account, "Previous Main")
        companion = store.create_character(account, "Saved Companion")
        generation = store.begin_session(account)
        store.select_character(account, generation, previous["id"])
        heroes.add(store, account, generation, previous["id"], companion["id"])
        encoded = b"New Main"
        body = (
            struct.pack(">qhB", -1, 3, len(encoded))
            + encoded
            + b"\x01"
            + appearance_section({"sex": 0, "clothIndex": 1, "skinColor": -9065766})
        )
        status, created = create(store, account, generation, body)
        self.assertEqual(0, status)
        selected = select_created(store, account, generation, created["id"])
        roster = heroes.ensure_company_party(store, account, generation, selected["id"])
        self.assertEqual(created["id"], roster["leader"]["id"])
        self.assertEqual((companion["id"],), tuple(c["id"] for c in roster["heroes"]))
        self.assertEqual(-9065766, selected["appearance"]["skinColor"])
        with store.connection() as db:
            party = db.execute(
                "SELECT p.leader_id FROM player_parties p JOIN player_party_members m "
                "ON m.party_id=p.id WHERE m.character_id=%s",
                (selected["id"],),
            ).fetchone()
            self.assertEqual(selected["id"], party["leader_id"])

    def test_protocol_creation_persistence_errors_and_session_ownership(self):
        store = self.store
        store.max_characters = 5
        account = store.register("creator", "creation-password")["id"]
        generation = store.begin_session(account)

        def request(name, character_id=-1):
            encoded = name.encode()
            return (
                struct.pack(">qhB", character_id, 2, len(encoded))
                + encoded
                + b"\x01"
                + appearance_section(
                    {"skinColor": -1, "sex": 0, "faceIndex": 3, "clothIndex": 0}
                )
            )

        status, char = create(store, account, generation, request("Fresh"))
        self.assertEqual(status, 0)
        self.assertEqual(char["appearance"]["skinColor"], -1)
        self.assertEqual(
            create(store, account, generation, request("Fresh")), (102, None)
        )
        self.assertEqual(create(store, account, generation, request("12")), (103, None))
        self.assertEqual(
            create(store, account, generation, request("Modify", char["id"])),
            (101, None),
        )
        for name in ("Second", "Third", "Fourth", "Fifth"):
            self.assertEqual(create(store, account, generation, request(name))[0], 0)
        self.assertEqual(
            create(store, account, generation, request("Sixth")), (104, None)
        )
        store.begin_session(account)
        with self.assertRaises(ValueError):
            create(store, account, generation, request("Stale"))
