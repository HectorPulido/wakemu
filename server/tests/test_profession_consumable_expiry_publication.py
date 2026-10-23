"""Profession reads leave consumable retirement to the publishing lifecycle."""
from postgres_case import PostgresCase
from test_consumable_session_lifecycle import ConsumableSessionLifecycleTests


class ProfessionConsumableExpiryPublicationTests(PostgresCase):
    fixture = ConsumableSessionLifecycleTests.fixture

    def test_profession_read_preserves_hero_expiry_publication_and_health(self):
        self.expiry_case(use_main=False)

    def test_profession_read_preserves_main_expiry_publication_and_health(self):
        self.expiry_case(use_main=True)

    def expiry_case(self, *, use_main):
        from wakfu_server.consumable_buffs import apply_states, evaluated_states
        from wakfu_server.consumable_characteristics import reconcile_health
        from wakfu_server.consumable_world_lifecycle import synchronize
        from wakfu_server.profession_consumable_modifiers import modifiers

        account, generation, main, hero = self.fixture()
        if use_main:
            hero = main
        with self.store.connection() as db:
            db.execute("DELETE FROM character_consumable_buffs")
            state = db.execute(
                "SELECT plan->'states'->0 AS state FROM native_consumable_actions WHERE item_ref=10376"
            ).fetchone()["state"]
            apply_states(
                self.store,
                db,
                hero["id"],
                [state],
                source_item_ref=10376,
                source_item_uid=hero["id"],
                generation=generation,
            )
            before_hero = reconcile_health(
                db, self.store.character(account, hero["id"], db)
            )
            db.execute(
                "UPDATE character_consumable_buffs SET remaining_ms=1000 WHERE character_id=%s",
                (hero["id"],),
            )
            stored_before = dict(
                db.execute(
                    "SELECT * FROM character_consumable_buffs WHERE character_id=%s",
                    (hero["id"],),
                ).fetchone()
            )
        previous = self.store.character(account, main["id"])
        self.store.clock = lambda: 1002
        with self.store.connection() as db:
            result = modifiers(
                self.store,
                db,
                hero["id"],
                64,
                generation=generation,
                is_battleground=False,
            )
            self.assertTrue(all(value == 0 for value in result.values()))
            self.assertEqual(
                evaluated_states(self.store, db, hero["id"], generation=generation), ()
            )
            count = db.execute(
                "SELECT count(*) AS n FROM character_consumable_buffs WHERE character_id=%s",
                (hero["id"],),
            ).fetchone()["n"]
            stored_after = db.execute(
                "SELECT * FROM character_consumable_buffs WHERE character_id=%s",
                (hero["id"],),
            ).fetchone()
        self.assertEqual(
            count, 1, "A profession lookup must not retire an unpublished hero state"
        )
        self.assertEqual(dict(stored_after), stored_before)
        updates = []
        updated = synchronize(
            self.store, account, generation, previous, company_updates=updates
        )
        self.assertEqual(len(updates), 0 if use_main else 1)
        old, saved = (previous, updated) if use_main else updates[0]
        self.assertEqual(saved["id"], hero["id"])
        self.assertEqual(old["consumable_states"][0]["state_id"], state["state_id"])
        self.assertEqual(saved["consumable_states"], ())
        self.assertEqual(saved["max_hp"], before_hero["max_hp"] - 20)
        self.assertEqual(saved["hp_damage"], before_hero["hp_damage"])
