import struct
import unittest

from postgres_case import PostgresCase


class CharacterDeletionCodecTests(unittest.TestCase):
    def test_native_cdn_request_is_one_positive_big_endian_character_id(self):
        from protocol_codec import decode_body

        body = struct.pack(">q", 0x0102030405060708)
        self.assertEqual(
            decode_body("out", 22870, body),
            {"character_id": 0x0102030405060708},
        )
        for malformed in (
            b"",
            body[:-1],
            body + b"\x00",
            bytes(8),
            struct.pack(">q", -1),
        ):
            with self.subTest(body=malformed), self.assertRaises(ValueError):
                decode_body("out", 22870, malformed)


class CharacterDeletionTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("char-delete-owner", "test-password")["id"]
        self.other_account = self.store.register("char-delete-other", "test-password")[
            "id"
        ]
        self.target = self.store.create_character(self.account, "Delete Target")
        self.generation = self.store.begin_session(self.account)

    def _party(self, members, leader):
        with self.store.connection() as db:
            party_id = db.execute(
                "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING id",
                (leader,),
            ).fetchone()["id"]
            for character_id in members:
                db.execute(
                    "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                    (character_id, party_id),
                )
        return party_id

    def test_deletion_hides_character_frees_name_and_slot_and_preserves_identity_rows(
        self,
    ):
        target_id = self.target["id"]
        self.store.max_characters = 1
        with self.assertRaisesRegex(ValueError, "Máximo 1 personajes"):
            self.store.create_character(self.account, "Second Before Delete")
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_progression SET xp=777 WHERE character_id=%s",
                (target_id,),
            )
            wallet_before = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s",
                (self.account,),
            ).fetchone()["kamas"]

        result = self.store.delete_character(self.account, self.generation, target_id)
        self.assertEqual(result["character_id"], target_id)
        self.assertIsNone(result["party_change"])
        self.assertEqual(self.store.characters(self.account), [])
        with self.assertRaisesRegex(ValueError, "Personaje no encontrado"):
            self.store.character(self.account, target_id)
        with self.assertRaisesRegex(ValueError, "Personaje no encontrado"):
            self.store.select_character(self.account, self.generation, target_id)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT deleted_at FROM characters WHERE id=%s", (target_id,)
            ).fetchone()
            self.assertIsNotNone(row["deleted_at"])
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (target_id,),
                ).fetchone()["xp"],
                777,
            )
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                wallet_before,
            )
            self.assertEqual(
                db.execute(
                    "SELECT character_id FROM inventory_initialized WHERE character_id=%s",
                    (target_id,),
                ).fetchone()["character_id"],
                target_id,
            )
        recreated = self.store.create_character(self.account, "Delete Target")
        self.assertNotEqual(recreated["id"], target_id)
        self.assertEqual(
            [c["id"] for c in self.store.characters(self.account)], [recreated["id"]]
        )

    def test_selection_and_deletion_race_has_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        barrier = Barrier(2)

        def select():
            barrier.wait(timeout=5)
            try:
                return self.store.select_character(
                    self.account, self.generation, self.target["id"]
                )
            except ValueError:
                return None

        def delete():
            barrier.wait(timeout=5)
            try:
                return self.store.delete_character(
                    self.account, self.generation, self.target["id"]
                )
            except ValueError:
                return None

        with ThreadPoolExecutor(max_workers=2) as workers:
            selected, deleted = list(workers.map(lambda fn: fn(), (select, delete)))
        with self.store.connection() as db:
            state = db.execute(
                "SELECT c.deleted_at,s.character_id FROM characters c "
                "JOIN sessions s ON s.account_id=c.account_id "
                "WHERE c.id=%s AND s.generation=%s",
                (self.target["id"], self.generation),
            ).fetchone()
        if state["deleted_at"] is None:
            self.assertIsNotNone(selected)
            self.assertIsNone(deleted)
            self.assertEqual(state["character_id"], self.target["id"])
        else:
            self.assertIsNone(selected)
            self.assertIsNotNone(deleted)
            self.assertIsNone(state["character_id"])

    def test_deleted_name_is_not_resolvable_as_social_identity(self):
        from wakfu_server.social_contacts import SocialContacts

        other_generation = self.store.begin_session(self.other_account)
        self.store.delete_character(self.account, self.generation, self.target["id"])
        contacts = SocialContacts(self.store)
        with self.assertRaisesRegex(ValueError, "Contact character not found"):
            contacts.add_friend(self.other_account, other_generation, "Delete Target")
        replacement = self.store.create_character(self.account, "Delete Target")
        self.assertEqual(
            contacts.add_friend(self.other_account, other_generation, "Delete Target")[
                "account_id"
            ],
            self.account,
        )
        self.assertEqual(replacement["name"], "Delete Target")

    def test_delete_requires_owned_live_unselected_session_and_does_not_partially_hide(
        self,
    ):
        with self.assertRaisesRegex(ValueError, "Return to character selection"):
            self.store.delete_character(
                self.account, "wrong-generation", self.target["id"]
            )
        self.store.select_character(self.account, self.generation, self.target["id"])
        with self.assertRaisesRegex(ValueError, "Return to character selection"):
            self.store.delete_character(
                self.account, self.generation, self.target["id"]
            )
        self.store.clear_character(self.account, self.generation)
        other_generation = self.store.begin_session(self.other_account)
        with self.assertRaisesRegex(ValueError, "not found"):
            self.store.delete_character(
                self.other_account, other_generation, self.target["id"]
            )
        self.assertEqual(len(self.store.characters(self.account)), 1)

    def test_active_fight_rejects_deletion_without_changing_character_or_session(self):
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, self.target["id"], self.account),
            )
        with self.assertRaisesRegex(ValueError, "active fight"):
            self.store.delete_character(
                self.account, self.generation, self.target["id"]
            )
        self.assertEqual(len(self.store.characters(self.account)), 1)
        self.assertFalse(
            self.store.current_character_session(
                self.account, self.generation, self.target["id"]
            )
        )

    def test_party_exit_is_atomic_and_disbands_a_two_member_party(self):
        second = self.store.create_character(self.account, "Delete Partner")
        party_id = self._party([self.target["id"], second["id"]], self.target["id"])
        result = self.store.delete_character(
            self.account, self.generation, self.target["id"]
        )
        change = result["party_change"]
        self.assertEqual(change["party_id"], party_id)
        self.assertEqual(change["removed"], [self.target["id"], second["id"]])
        self.assertEqual(change["remaining"], [])

        class RecordingWorld:
            def __init__(self):
                self.sent = []

            def live_identity(self, character_id):
                if character_id == second["id"]:
                    return "peer-generation", {"id": character_id}
                return None

            def send_to(self, character_id, generation, opcode, body):
                self.sent.append((character_id, generation, opcode, body))
                return True

        from wakfu_server.party_dispatch import Parties

        world = RecordingWorld()
        Parties(self.store, world).publish_character_deletion(change)
        self.assertEqual(len(world.sent), 1)
        self.assertEqual(world.sent[0][:3], (second["id"], "peer-generation", 1049))
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT id FROM player_parties WHERE id=%s", (party_id,)
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                    (party_id,),
                ).fetchone()["n"],
                0,
            )

    def test_deletion_preserves_a_three_member_party_and_promotes_oldest_member(self):
        second = self.store.create_character(self.account, "Delete Partner")
        third = self.store.create_character(self.account, "Delete Witness")
        party_id = self._party(
            [self.target["id"], second["id"], third["id"]], self.target["id"]
        )
        result = self.store.delete_character(
            self.account, self.generation, self.target["id"]
        )
        self.assertEqual(
            result["party_change"]["remaining"], [second["id"], third["id"]]
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT leader_id FROM player_parties WHERE id=%s", (party_id,)
                ).fetchone()["leader_id"],
                second["id"],
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                    (party_id,),
                ).fetchone()["n"],
                2,
            )

    def test_active_exchange_and_craft_block_deletion(self):
        peer = self.store.create_character(self.other_account, "Exchange Partner")
        peer_generation = self.store.begin_session(self.other_account)
        self.store.select_character(self.other_account, peer_generation, peer["id"])
        self.store.select_character(self.account, self.generation, self.target["id"])
        from wakfu_server.items import player_exchanges

        exchange = player_exchanges.invite(
            self.store, self.account, self.generation, self.target["id"], peer["id"]
        )
        self.store.clear_character(self.account, self.generation)
        with self.assertRaisesRegex(ValueError, "active exchange"):
            self.store.delete_character(
                self.account, self.generation, self.target["id"]
            )
        from datetime import timedelta

        with self.store.connection() as db:
            db.execute(
                "UPDATE player_exchanges SET state='active',created_at=%s,expires_at=%s WHERE id=%s",
                (self.store.now(-120), self.store.now(-60), exchange["id"]),
            )
        with self.assertRaisesRegex(ValueError, "active exchange"):
            self.store.delete_character(
                self.account, self.generation, self.target["id"]
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE player_exchanges SET state='canceled' WHERE id=%s",
                (exchange["id"],),
            )
            db.execute(
                "DELETE FROM player_exchange_members WHERE exchange_id=%s",
                (exchange["id"],),
            )
            db.execute(
                "DELETE FROM player_exchange_outbox WHERE exchange_id=%s",
                (exchange["id"],),
            )
            db.execute("DELETE FROM player_exchanges WHERE id=%s", (exchange["id"],))
            # A minimal valid active craft occupation is enough to verify the
            # guard; no crafting worker or inventory mutation is exercised.
            now = self.store.now()
            db.execute(
                "INSERT INTO craft_occupations(token,account_id,generation,character_id,table_uid,map_id,instance_id,definition_id,profession_id,recipe_id,request_opcode,batch_count,request_hash,inventory_snapshot,duration_ms,started_at,due_at) "
                "VALUES(gen_random_uuid(),%s,%s,%s,1,1,0,1,1,1,12231,1,%s,'{}',1000,%s,%s)",
                (
                    self.account,
                    self.generation,
                    self.target["id"],
                    bytes(32),
                    now,
                    now + timedelta(seconds=1),
                ),
            )
        with self.assertRaisesRegex(ValueError, "active craft"):
            self.store.delete_character(
                self.account, self.generation, self.target["id"]
            )
        self.assertEqual(len(self.store.characters(self.account)), 1)
