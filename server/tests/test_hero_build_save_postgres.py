"""Build edits authorize the real selected account roster transactionally."""
import unittest
from postgres_case import PostgresCase
from wakfu_server.wire import proto_field


class HeroBuildSavePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("hero_builder", "local-test-password")["id"]
        self.main = self.store.create_character(self.account, "MainBuilder", breed=8)
        self.hero = self.store.create_character(self.account, "HeroBuilder", breed=8)
        self.generation = self.store.begin_session(self.account, ttl=10000)
        self.store.select_character(self.account, self.generation, self.main["id"])

    def save(self, identity, generation=None):
        from wakfu_server import builds

        return self.store.save_build(
            self.account,
            generation or self.generation,
            identity,
            0,
            dict(
                sheet=b"".join(
                    proto_field(t, v)
                    for t, v in [
                        (8, 0),
                        (18, b"Default"),
                        (24, (1 << 64) - 1),
                        (56, 1),
                        (64, 0),
                    ]
                ),
                equipment=builds.EMPTY_EQUIPMENT,
                deck=b"",
                aptitudes=builds.EMPTY_APTITUDES,
            ),
        )

    def test_active_owned_hero_build_persists_without_switching_main(self):
        from wakfu_server.characters.heroes import add

        add(self.store, self.account, self.generation, self.main["id"], self.hero["id"])
        saved = self.save(self.hero["id"])
        self.assertIn(0, saved["builds"])
        self.assertTrue(
            self.store.current_character_session(
                self.account, self.generation, self.main["id"]
            )
        )
        self.assertFalse(
            self.store.current_character_session(
                self.account, self.generation, self.hero["id"]
            )
        )

    def test_inactive_owned_hero_is_rejected(self):
        with self.assertRaises(ValueError):
            self.save(self.hero["id"])
        self.assertEqual(
            self.store.character(self.account, self.hero["id"])["builds"], {}
        )

    def test_foreign_character_is_rejected(self):
        other = self.store.register("foreign_builder", "local-test-password")["id"]
        foreign = self.store.create_character(other, "ForeignBuilder", breed=8)
        with self.assertRaises(ValueError):
            self.save(foreign["id"])
        self.assertEqual(self.store.character(other, foreign["id"])["builds"], {})

    def test_expired_generation_cannot_save(self):
        with self.assertRaises(ValueError):
            self.save(self.main["id"], generation="stale-generation")


if __name__ == "__main__":
    unittest.main()
