import unittest
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server import health_policy, health_store
from wakfu_server.characters import heroes


class HeroBlackScreenRegressionTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("black-screen-owner", "test-password")["id"]
        self.main = self.store.create_character(self.account, "Selected Main")
        self.hero = self.store.create_character(self.account, "Fresh Hero")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])

    def _regen(self, character_id):
        with self.store.connection() as db:
            return db.execute(
                "SELECT initial_hp,initial_damage,coefficient FROM character_regeneration WHERE character_id=%s",
                (character_id,),
            ).fetchone()

    def test_never_selected_hero_switch_initializes_regen_and_tick_preserves_wounds(
        self,
    ):
        with self.store.connection() as db:
            hero = self.store.character(self.account, self.hero["id"], db)
            health_policy.apply(db, hero, hero["hp"] - 17)
        self.assertIsNone(self._regen(self.hero["id"]))
        heroes.add(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )
        self.assertIsNone(self._regen(self.hero["id"]))

        switched = heroes.switch_main(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )
        self.assertEqual(self.hero["id"], switched["leader"]["id"])
        state = self._regen(self.hero["id"])
        self.assertIsNotNone(state)
        self.assertEqual(17, state["initial_damage"])
        now_ms = int(self.store.clock() * 1000)
        ticked = health_store.tick(
            self.store,
            self.account,
            self.generation,
            self.hero["id"],
            switched["leader"]["hp"],
            now_ms=now_ms + 1000,
        )
        self.assertEqual(switched["leader"]["hp"], ticked["hp"])
        self.assertEqual(
            17, self.store.character(self.account, self.hero["id"])["hp_damage"]
        )

    def test_switch_initialization_failure_rolls_back_session_roster_and_slot(self):
        heroes.add(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )
        with patch(
            "wakfu_server.health_store.initialize",
            side_effect=RuntimeError("injected initialize failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected initialize failure"):
                heroes.switch_main(
                    self.store,
                    self.account,
                    self.generation,
                    self.main["id"],
                    self.hero["id"],
                )
        with self.store.connection() as db:
            self.assertEqual(
                self.main["id"],
                db.execute(
                    "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s",
                    (self.account, self.generation),
                ).fetchone()["character_id"],
            )
            self.assertEqual(
                self.main["id"],
                db.execute(
                    "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["leader_id"],
            )
            self.assertEqual(
                self.hero["id"],
                db.execute(
                    "SELECT character_id FROM account_hero_slots WHERE account_id=%s AND slot=0",
                    (self.account,),
                ).fetchone()["character_id"],
            )
        self.assertIsNone(self._regen(self.hero["id"]))

    def test_dead_hero_switch_remains_dead_and_regeneration_stays_disabled(self):
        heroes.add(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )
        with self.store.connection() as db:
            hero = self.store.character(self.account, self.hero["id"], db)
            health_policy.apply(db, hero, 0)
        switched = heroes.switch_main(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )
        self.assertEqual(0, switched["leader"]["hp"])
        self.assertEqual(0, self._regen(self.hero["id"])["coefficient"])
        ticked = health_store.tick(
            self.store,
            self.account,
            self.generation,
            self.hero["id"],
            0,
            now_ms=int(self.store.clock() * 1000) + 60000,
        )
        self.assertEqual(0, ticked["hp"])
        self.assertTrue(
            self.store.character(self.account, self.hero["id"])["health_dead"]
        )
