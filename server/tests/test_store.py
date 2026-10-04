import concurrent.futures
from pathlib import Path
import tempfile
import unittest
from wakfu_server.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1000
        self.store = Store(Path(self.temp.name) / "world.sqlite3", lambda: self.now)
        self.a = self.store.register("alice", "experiment-alice")["id"]
        self.b = self.store.register("bob", "experiment-bob")["id"]

    def tearDown(self):
        self.temp.cleanup()

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
        reopened = Store(self.store.path)
        self.assertEqual(
            reopened.character(self.a, char["id"])["appearance"], appearance
        )
        self.assertEqual((char["face"], char["hair"], char["sex"]), (3, 0, 0))
        for bad in ({"skinColor": 1 << 31}, {"sex": True}, {"unknown": 0}):
            with self.assertRaises(ValueError):
                reopened.create_character(self.a, "Invalid", appearance=bad)

    def test_legacy_appearance_fallback_and_idempotent_migration(self):
        char = self.store.create_character(
            self.a, "Legacy", colors=[0x123456, 0, 0xFFFFFF]
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET appearance='{}' WHERE id=?", (char["id"],)
            )
        reopened = Store(self.store.path)
        result = reopened.character(self.a, char["id"])
        self.assertEqual(result["appearance"]["skinColor"], -15584170)
        self.assertEqual(result["appearance"]["pupilColor"], -1)

    def test_passwords_and_account_ownership(self):
        self.assertEqual(
            self.store.authenticate("ALICE", "experiment-alice")["id"], self.a
        )
        with self.assertRaises(ValueError):
            self.store.authenticate("alice", "wrong")
        with self.assertRaises(ValueError):
            self.store.register("Alice", "another-password")
        char = self.store.create_character(self.a, "Alpha")
        self.assertEqual((char["level"], char["hp"], char["map_id"]), (1, 50, 1134))
        with self.assertRaises(ValueError):
            self.store.character(self.b, char["id"])
        with self.store.connection() as db:
            self.assertNotIn(
                b"experiment-alice",
                bytes(
                    db.execute(
                        "SELECT password_hash FROM accounts WHERE id=?", (self.a,)
                    ).fetchone()[0]
                ),
            )

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
        new = self.store.begin_session(self.a)
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
        reopened = Store(self.store.path, lambda: self.now)
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
                db.execute("SELECT digest FROM tokens").fetchone()[0], token
            )
        self.now += 6
        with self.assertRaises(ValueError):
            self.store.token(token, "game")


if __name__ == "__main__":
    unittest.main()
