import concurrent.futures
import unittest
from postgres_case import PostgresCase


class StoreTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = 1000
        self.store.clock = lambda: self.now
        self.store.max_characters = 5
        self.a = self.store.register("alice", "experiment-alice")["id"]
        self.b = self.store.register("bob", "experiment-bob")["id"]

    def test_native_playable_classes_include_huppermage_but_not_soul(self):
        character = self.store.create_character(self.a, "Hupper Test", breed=19)
        self.assertEqual(character["breed"], 19)
        for breed in (17, 0, 20, True):
            with self.assertRaises(ValueError):
                self.store.create_character(self.a, "Invalid Breed", breed=breed)

    def test_configured_selection_capacity_keeps_account_isolation_and_limit(self):
        expanded = self.reopen()
        expanded.clock = lambda: self.now
        expanded.max_characters = 24
        names = ["Character " + chr(ord("A") + index) for index in range(24)]
        for name in names:
            expanded.create_character(self.a, name)
        self.assertEqual(len(expanded.characters(self.a)), 24)
        self.assertEqual(expanded.characters(self.b), [])
        with self.assertRaisesRegex(ValueError, "Máximo 24"):
            expanded.create_character(self.a, "One Extra")

    def test_expanded_default_applies_to_existing_and_new_accounts(self):
        from unittest.mock import patch
        import os
        from wakfu_server.characters.selection_capacity import packet

        self.store.create_character(self.a, "Existing Character")
        with patch.dict(os.environ, {"WAKFU_MAX_CHARACTERS": "18"}):
            expanded = self.reopen()
        new_account = expanded.register("new-capacity", "test-password")["id"]
        for account, prefix in ((self.a, "Existing"), (new_account, "New")):
            for letter in "ABCDEF":
                expanded.create_character(account, prefix + " Slot " + letter)
            self.assertGreater(len(expanded.characters(account)), 5)
            self.assertEqual(packet(expanded.max_characters), (23992, b"\x0d"))
        self.assertEqual(len(expanded.characters(self.a)), 7)
        self.assertEqual(len(expanded.characters(new_account)), 6)
        self.assertEqual(expanded.characters(self.b), [])

    def test_native_maximum_rejects_character_128_without_changing_roster(self):
        self.store.max_characters = 127
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,"
                "colors,appearance,hp,max_hp) SELECT %s,'Capacity ' || n,"
                "'capacity ' || n,2,false,0,0,'[]'::jsonb,'{}'::jsonb,1,1 "
                "FROM generate_series(1,127) AS n",
                (self.a,),
            )
        with self.assertRaisesRegex(ValueError, "Máximo 127"):
            self.store.create_character(self.a, "Overflow Character")
        # These boundary rows intentionally omit progression and wallet
        # records, so count their persisted roster rows without hydrating them.
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS total FROM characters "
                    "WHERE account_id=%s AND deleted_at IS NULL",
                    (self.a,),
                ).fetchone()["total"],
                127,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS total FROM characters "
                    "WHERE account_id=%s AND deleted_at IS NULL",
                    (self.b,),
                ).fetchone()["total"],
                0,
            )

    def test_signed_appearance_survives_reopen_without_losing_costume_colors(self):
        appearance = {
            "skinColor": -6720193,
            "hairColor": -10873225,
            "pupilColor": -16777216,
            "costumeColor1": -4209466,
            "costumeColor6": -12229251,
            "sex": 0,
            "faceIndex": 3,
            "clothIndex": 0,
        }
        char = self.store.create_character(
            self.a, "Fresh Cra", breed=2, appearance=appearance
        )
        reopened = self.reopen()
        self.assertEqual(
            reopened.character(self.a, char["id"])["appearance"], appearance
        )
        self.assertEqual((char["face"], char["hair"], char["sex"]), (3, 0, 0))
        for bad in ({"skinColor": 1 << 31}, {"sex": True}, {"unknown": 0}):
            with self.assertRaises(ValueError):
                reopened.create_character(self.a, "Invalid", appearance=bad)

    def test_passwords_and_account_ownership(self):
        self.assertEqual(
            self.store.authenticate("ALICE", "experiment-alice")["id"], self.a
        )
        with self.assertRaises(ValueError):
            self.store.authenticate("alice", "wrong")
        with self.assertRaises(ValueError):
            self.store.register("Alice", "another-password")
        char = self.store.create_character(self.a, "Alpha")
        self.assertEqual(
            (char["level"], char["hp"], char["map_id"]), (1, char["max_hp"], 1134)
        )
        with self.assertRaises(ValueError):
            self.store.character(self.b, char["id"])
        with self.store.connection() as db:
            self.assertNotIn(
                b"experiment-alice",
                bytes(
                    db.execute(
                        "SELECT password_hash FROM accounts WHERE id=%s", (self.a,)
                    ).fetchone()["password_hash"]
                ),
            )

    def test_character_hydrates_authoritative_account_admin_role(self):
        admin_character = self.store.create_character(self.a, "Admin Chat Role")
        ordinary_character = self.store.create_character(self.b, "Ordinary Chat Role")
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=true WHERE id=%s", (self.a,))

        admin = self.store.character(self.a, admin_character["id"])
        ordinary = self.store.character(self.b, ordinary_character["id"])
        self.assertIs(admin["account_is_admin"], True)
        self.assertIs(ordinary["account_is_admin"], False)

        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=false WHERE id=%s", (self.a,))
        refreshed = self.store.character(self.a, admin_character["id"])
        self.assertIs(refreshed["account_is_admin"], False)

    def test_one_use_token_under_race(self):
        token = self.store.issue_token(self.a, "ticket")

        def consume(_):
            try:
                self.store.token(token, "ticket", consume=True)
                return True
            except ValueError:
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(consume, range(8))), 1)

    def test_replacement_and_late_cleanup(self):
        old = self.store.begin_session(self.a)
        # The deterministic clock advances by 61 seconds below.
        new = self.store.begin_session(self.a, ttl=60)
        self.store.end_session(self.a, old)
        self.assertFalse(self.store.current_session(self.a, old))
        self.assertTrue(self.store.current_session(self.a, new))
        self.now += 61
        self.assertFalse(self.store.heartbeat(self.a, new))

    def test_character_switch_keeps_session_and_revokes_old_movement(self):
        first = self.store.create_character(self.a, "First")
        second = self.store.create_character(self.a, "Second")
        generation = self.store.begin_session(self.a)
        self.store.select_character(self.a, generation, first["id"])
        self.store.clear_character(self.a, generation)
        self.assertTrue(self.store.current_session(self.a, generation))
        start = {key: first[key] for key in ("x", "y", "z")}
        with self.assertRaises(ValueError):
            self.store.move(self.a, generation, first["id"], start, start)
        self.assertEqual(
            self.store.select_character(self.a, generation, second["id"])["id"],
            second["id"],
        )
        newer = self.store.begin_session(self.a)
        with self.assertRaises(ValueError):
            self.store.clear_character(self.a, generation)
        self.assertTrue(self.store.current_session(self.a, newer))

    def test_concurrent_characters_are_isolated_and_persistent(self):
        def create(name):
            return self.store.create_character(self.a, name)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            characters = list(
                pool.map(create, ["Alpha", "Bravo", "Charlie", "Delta", "Echo"])
            )
        self.assertEqual(len({c["id"] for c in characters}), 5)
        with self.assertRaises(ValueError):
            self.store.create_character(self.a, "Foxtrot")
        char = characters[0]
        generation = self.store.begin_session(self.a)
        self.store.select_character(self.a, generation, char["id"])
        start = {k: char[k] for k in ("x", "y", "z")}
        end = dict(x=-14, y=-8, z=-1)
        self.store.move(self.a, generation, char["id"], start, end)
        reopened = self.reopen()
        self.assertEqual(reopened.character(self.a, char["id"])["x"], -14)
        with self.assertRaises(ValueError):
            self.store.move(self.a, generation, char["id"], start, end)
        other = self.store.begin_session(self.b)
        with self.assertRaises(ValueError):
            self.store.select_character(self.b, other, char["id"])

    def test_token_expiry_and_no_plain_tokens_in_database(self):
        token = self.store.issue_token(self.a, "game", ttl=5)
        with self.store.connection() as db:
            self.assertNotEqual(
                db.execute("SELECT digest FROM tokens").fetchone()["digest"], token
            )
        self.now += 6
        with self.assertRaises(ValueError):
            self.store.token(token, "game")


if __name__ == "__main__":
    unittest.main()
