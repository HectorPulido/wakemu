import struct
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server.characters import hero_wire, nation_state, social


class NationCodecTests(unittest.TestCase):
    def test_public_chooser_command_and_exact_native_list(self):
        self.assertTrue(nation_state.local_selection_request(" !NACION "))
        for text in ("!naciones", "hola", ""):
            self.assertFalse(nation_state.local_selection_request(text))
        with self.assertRaisesRegex(ValueError, "Uso"):
            nation_state.local_selection_request("!nacion 30")
        opcode, body = nation_state.selection_packet({30: 1, 31: 2, 34: 1})
        self.assertEqual(opcode, 14006)
        self.assertEqual(struct.unpack_from(">i", body)[0], 4)
        self.assertEqual(len(body), 100)
        for index, identity in enumerate((30, 31, 32, 33)):
            row = struct.unpack_from(">iifiii", body, 4 + index * 24)
            self.assertEqual(
                row, (identity, 0, {30: 0.25, 31: 0.5}.get(identity, 0), 0, 0, 0)
            )
        with self.assertRaises(ValueError):
            nation_state.selection_packet({1: 1})

    def test_native_ids_and_exact_enrollment_layout(self):
        for value in (30, 31, 32, 33):
            body = struct.pack(">i", value) + bytes(2)
            self.assertEqual(nation_state.decode_enrollment(body), value)
            self.assertEqual(nation_state.nation_id({"nation_id": value}), value)
            self.assertEqual(nation_state.synchro({"nation_id": value}), bytes(27))
        for body in (
            bytes(6),
            struct.pack(">i", 1) + bytes(2),
            struct.pack(">i", 30),
            struct.pack(">i", 30) + b"\0\1",
        ):
            with self.assertRaises(ValueError):
                nation_state.decode_enrollment(body)
        self.assertEqual(nation_state.nation_id({"nation_id": 34}), 34)
        with self.assertRaises(ValueError):
            nation_state.decode_enrollment(struct.pack(">i", 34) + bytes(2))
        for value in (True, -1, 1, 35, "30"):
            with self.assertRaises(ValueError):
                nation_state.nation_id({"nation_id": value})

    def test_company_uses_authoritative_character_nation(self):
        self.assertEqual(
            struct.unpack_from(
                ">i",
                social.company(
                    7,
                    {
                        "id": 9,
                        "nation_id": 32,
                    },
                ),
                16,
            )[0],
            32,
        )
        self.assertEqual(nation_state.nation_id(None), 0)
        opcode, body = hero_wire.company(7, 9, nation_id=34)
        self.assertEqual(opcode, 13873)
        self.assertEqual(struct.unpack_from(">i", body, 24)[0], 34)


class NationPersistenceTests(PostgresCase):
    def test_enrollment_is_durable_character_scoped_and_cannot_reenroll(self):
        account = self.store.register("nation" + uuid.uuid4().hex[:10], "password")[
            "id"
        ]
        first = self.store.create_character(account, "NationAlpha")
        sibling = self.store.create_character(account, "NationBravo")
        generation = self.store.begin_session(account, ttl=10000)
        self.store.select_character(account, generation, first["id"])
        self.assertEqual(
            nation_state.open_selection(self.store, account, generation, first["id"]),
            nation_state.selection_packet({}),
        )
        enrolled = nation_state.enroll(
            self.store,
            account,
            generation,
            first["id"],
            struct.pack(">i", 30) + bytes(2),
        )
        self.assertEqual(enrolled["nation_id"], 30)
        with self.assertRaises(ValueError):
            nation_state.open_selection(self.store, account, generation, first["id"])
        self.assertEqual(self.reopen().character(account, first["id"])["nation_id"], 30)
        self.assertEqual(self.store.character(account, sibling["id"])["nation_id"], 0)
        with self.assertRaises(ValueError):
            nation_state.enroll(
                self.store,
                account,
                generation,
                first["id"],
                struct.pack(">i", 31) + bytes(2),
            )
        with self.assertRaises(ValueError):
            nation_state.enroll(
                self.store,
                account,
                generation,
                sibling["id"],
                struct.pack(">i", 31) + bytes(2),
            )
        generation = self.store.begin_session(account, ttl=10000)
        self.assertEqual(
            self.store.select_character(account, generation, first["id"])["nation_id"],
            30,
        )
        self.store.select_character(account, generation, sibling["id"])
        self.assertEqual(
            nation_state.open_selection(self.store, account, generation, sibling["id"]),
            nation_state.selection_packet({30: 1}),
        )
        with self.assertRaises(ValueError):
            nation_state.open_selection(self.store, account, "stale", sibling["id"])
        with self.assertRaises(ValueError):
            nation_state.enroll(
                self.store,
                account,
                "stale",
                first["id"],
                struct.pack(">i", 32) + bytes(2),
            )
