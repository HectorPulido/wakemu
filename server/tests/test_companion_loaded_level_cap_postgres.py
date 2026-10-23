"""PostgreSQL regression for companion cap from the loaded human company."""
import unittest
import uuid

from postgres_case import PostgresCase


class CompanionLoadedLevelCapPostgresTests(PostgresCase):
    def test_cap_uses_main_and_active_owned_heroes_only(self):
        from wakfu_server.characters import companions

        account = self.store.register(
            "companion-cap-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        main = self.store.create_character(account, "Cap Main")
        active = self.store.create_character(account, "Active Hero")
        inactive = self.store.create_character(account, "Inactive Hero")
        foreign_account = self.store.register(
            "companion-cap-foreign-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        foreign = self.store.create_character(foreign_account, "Foreign Hero")
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=20 WHERE id=%s", (main["id"],))
            db.execute("UPDATE characters SET level=80 WHERE id=%s", (active["id"],))
            db.execute("UPDATE characters SET level=230 WHERE id=%s", (inactive["id"],))
            db.execute("UPDATE characters SET level=230 WHERE id=%s", (foreign["id"],))
            db.execute(
                "INSERT INTO account_hero_rosters(account_id,leader_id) VALUES(%s,%s)",
                (account, main["id"]),
            )
            db.execute(
                "INSERT INTO account_hero_slots(account_id,slot,character_id) VALUES(%s,0,%s)",
                (account, active["id"]),
            )
            cap = companions.loaded_level_cap(db, self.store, account, main["id"])
            self.assertEqual(80, cap)

            db.execute(
                "DELETE FROM account_hero_slots WHERE account_id=%s AND character_id=%s",
                (account, active["id"]),
            )
            self.assertEqual(
                20, companions.loaded_level_cap(db, self.store, account, main["id"])
            )


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(CompanionLoadedLevelCapPostgresTests))
    return suite
