"""Original bHE companion activation and account collection transactions."""
import struct
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server.characters import companions
from wakfu_server.inventory_items import grant


class AccountCompanionActivationPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "companion-owner-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Companion Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )

    def _item(self, reference, slot):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=reference,
            quantity=1,
            container=self.container,
            slot=slot,
            allowed_references={reference},
        )

    @staticmethod
    def _request(action_id, uid):
        return struct.pack(">iq", action_id, uid)

    def _owned(self, uid):
        with self.store.connection() as db:
            return db.execute(
                "SELECT uid FROM inventory_items WHERE uid=%s AND character_id=%s",
                (uid, self.character["id"]),
            ).fetchone()

    def test_all_sixteen_activations_are_durable_and_replay_without_double_debit(self):
        descriptors = tuple(companions.descriptors().values())
        self.assertEqual(16, len(descriptors))
        for slot, item in enumerate(descriptors):
            with self.subTest(item_ref=item["item_ref"]):
                source = self._item(item["item_ref"], slot)
                body = self._request(item["action_id"], source["uid"])
                result = companions.use(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    body,
                    in_fight=False,
                )
                self.assertTrue(result["applied"])
                self.assertEqual(
                    ("bHE", 1), (result["native_class"], result["consumed"])
                )
                self.assertEqual(
                    [12470, 13954], [opcode for opcode, _ in result["packets"]]
                )
                self.assertIsNone(self._owned(source["uid"]))
                replay = companions.use(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    body,
                    in_fight=False,
                )
                self.assertFalse(replay["applied"])
                self.assertEqual(result["companion"]["id"], replay["companion"]["id"])
                self.assertIsNone(self._owned(source["uid"]))

        with self.store.connection() as db:
            rows = companions.collection(db, self.account)
        self.assertEqual(
            {row["breed_ref"] for row in descriptors},
            {row["breed_ref"] for row in rows},
        )
        opcode, payload = companions.collection_packet(rows)
        self.assertEqual(22790, opcode)
        self.assertEqual(16, payload[0])
        encoded = [companions.record(row) for row in rows]
        self.assertEqual(sum(map(len, encoded)), len(payload) - 1)
        self.assertTrue(payload[1:].startswith(encoded[0]))

    def test_foreign_wrong_action_combat_stale_and_duplicate_breed_preserve_item(self):
        descriptor = next(
            row for row in companions.descriptors().values() if row["item_ref"] == 17878
        )
        source = self._item(descriptor["item_ref"], 0)
        body = self._request(descriptor["action_id"], source["uid"])
        wrong = self._request(descriptor["action_id"] + 1, source["uid"])
        calls = (
            lambda: companions.use(
                self.store,
                self.account,
                "stale",
                self.character["id"],
                body,
                in_fight=False,
            ),
            lambda: companions.use(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                wrong,
                in_fight=False,
            ),
            lambda: companions.use(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                body,
                in_fight=True,
            ),
        )
        for call in calls:
            with self.assertRaises(ValueError):
                call()
            self.assertIsNotNone(self._owned(source["uid"]))

        result = companions.use(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            body,
            in_fight=False,
        )
        self.assertTrue(result["applied"])
        duplicate = self._item(descriptor["item_ref"], 1)
        with self.assertRaisesRegex(ValueError, "already owns that companion"):
            companions.use(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                self._request(descriptor["action_id"], duplicate["uid"]),
                in_fight=False,
            )
        self.assertIsNotNone(self._owned(duplicate["uid"]))

    def test_company_slots_are_two_per_owner_and_companions_are_not_shared(self):
        descriptors = tuple(companions.descriptors().values())[:3]
        identities = []
        for slot, descriptor in enumerate(descriptors):
            source = self._item(descriptor["item_ref"], slot)
            result = companions.use(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                self._request(descriptor["action_id"], source["uid"]),
                in_fight=False,
            )
            identities.append(result["companion"]["id"])
        first = companions.add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", identities[0]),
        )
        second = companions.add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", identities[1]),
        )
        self.assertTrue(first["applied"])
        self.assertTrue(second["applied"])
        self.assertEqual({0, 1}, {row["slot"] for row in second["companions"]})
        repeated = companions.add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", identities[0]),
        )
        self.assertFalse(repeated["applied"])
        with self.assertRaisesRegex(ValueError, "company slots are full"):
            companions.add_to_party(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">q", identities[2]),
            )

        removed = companions.remove_from_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            identities[0],
        )
        self.assertTrue(removed["applied"])
        moved = companions.add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", identities[2]),
        )
        self.assertTrue(moved["applied"])
        self.assertEqual(
            {identities[1], identities[2]}, {row["id"] for row in moved["companions"]}
        )

        other_character = self.store.create_character(self.account, "Companion Second")
        other_generation = self.store.begin_session(self.account)
        self.store.select_character(
            self.account, other_generation, other_character["id"]
        )
        with self.assertRaisesRegex(
            ValueError, "already belongs to another selected company"
        ):
            companions.add_to_party(
                self.store,
                self.account,
                other_generation,
                other_character["id"],
                struct.pack(">q", identities[1]),
            )


if __name__ == "__main__":
    unittest.main()
