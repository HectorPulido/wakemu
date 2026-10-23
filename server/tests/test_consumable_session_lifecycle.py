"""Observed session departures checkpoint every active owned food clock atomically."""
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server.characters import heroes
from wakfu_server.consumable_buffs import apply_states
from wakfu_server.consumable_world_lifecycle import synchronize


class ConsumableSessionLifecycleTests(PostgresCase):
    def fixture(self):
        self.store.clock = lambda: 1000
        account = self.store.register("sessionfoodclock", "local-password")["id"]
        main = self.store.create_character(account, "Session Food Main")
        hero = self.store.create_character(account, "Session Food Hero")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        with self.store.connection() as db:
            state = db.execute(
                "SELECT plan->'states'->0 AS state FROM native_consumable_actions WHERE item_ref=3663"
            ).fetchone()["state"]
            for actor in (main, hero):
                apply_states(
                    self.store,
                    db,
                    actor["id"],
                    [state],
                    source_item_ref=3663,
                    source_item_uid=actor["id"],
                    generation=generation,
                )
        return account, generation, main, hero

    def rows(self, account):
        with self.store.connection() as db:
            return list(
                db.execute(
                    "SELECT b.* FROM character_consumable_buffs b JOIN characters c ON c.id=b.character_id WHERE c.account_id=%s ORDER BY b.character_id",
                    (account,),
                )
            )

    def test_live_takeover_preserves_all_observed_company_time_and_pauses_offline(self):
        account, generation, main, hero = self.fixture()
        previous = self.store.character(account, main["id"])
        self.store.clock = lambda: 1002
        replacement = self.store.begin_session(account, previous_generation=generation)
        self.assertEqual(
            [(r["remaining_ms"], r["online_generation"]) for r in self.rows(account)],
            [(898000, None)] * 2,
        )
        synchronize(self.store, account, generation, previous, mode="pause")
        self.store.clock = lambda: 1100
        self.store.select_character(account, replacement, main["id"])
        resumed = synchronize(
            self.store,
            account,
            replacement,
            self.store.character(account, main["id"]),
            mode="resume",
        )
        self.assertEqual(resumed["consumable_states"][0]["remaining_ms"], 898000)
        self.store.clock = lambda: 1101
        synchronize(self.store, account, replacement, resumed)
        self.assertEqual([r["remaining_ms"] for r in self.rows(account)], [897000] * 2)

    def test_picker_pauses_current_company_and_same_generation_resume_is_exact(self):
        account, generation, main, hero = self.fixture()
        self.store.clock = lambda: 1002
        self.store.clear_character(account, generation)
        self.assertEqual(
            [(r["remaining_ms"], r["online_generation"]) for r in self.rows(account)],
            [(898000, None)] * 2,
        )
        self.store.clock = lambda: 1100
        self.store.select_character(account, generation, main["id"])
        current = synchronize(
            self.store,
            account,
            generation,
            self.store.character(account, main["id"]),
            mode="resume",
        )
        self.assertEqual(current["consumable_states"][0]["remaining_ms"], 898000)

    def test_missing_live_observation_does_not_charge_an_unknown_offline_gap(self):
        account, generation, main, hero = self.fixture()
        self.store.clock = lambda: 1100
        replacement = self.store.begin_session(account)
        self.store.select_character(account, replacement, main["id"])
        synchronize(
            self.store,
            account,
            replacement,
            self.store.character(account, main["id"]),
            mode="resume",
        )
        self.assertEqual([r["remaining_ms"] for r in self.rows(account)], [900000] * 2)

    def test_departure_and_clock_accounting_roll_back_together_on_failure(self):
        from wakfu_server import consumable_session_lifecycle

        account, generation, main, hero = self.fixture()
        initial = self.rows(account)
        original = consumable_session_lifecycle.pause_current_company
        self.store.clock = lambda: 1002

        def fail_after_pause(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("departure rollback")

        for depart in (
            lambda: self.store.begin_session(account, previous_generation=generation),
            lambda: self.store.clear_character(account, generation),
        ):
            with patch.object(
                consumable_session_lifecycle, "pause_current_company", fail_after_pause
            ):
                with self.assertRaisesRegex(RuntimeError, "departure rollback"):
                    depart()
            self.assertEqual(self.rows(account), initial)
            self.assertTrue(
                self.store.current_character_session(account, generation, main["id"])
            )
