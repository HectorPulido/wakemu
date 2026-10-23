"""Online food clocks follow active company membership atomically."""
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.characters import heroes
from wakfu_server.consumable_buffs import apply_states
from wakfu_server.consumable_world_lifecycle import synchronize


class ConsumableCompanyMembershipTests(PostgresCase):
    def fixture(self):
        self.store.clock = lambda: 1000
        account = self.store.register("companyfoodclock", "local-password")["id"]
        main = self.store.create_character(account, "Clock Main")
        hero = self.store.create_character(account, "Clock Hero")
        other = self.store.create_character(account, "Clock Other")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        with self.store.connection() as db:
            state = db.execute(
                "SELECT plan->'states'->0 AS state FROM native_consumable_actions WHERE item_ref=3663"
            ).fetchone()["state"]
            for actor in (main, hero, other):
                apply_states(
                    self.store,
                    db,
                    actor["id"],
                    [state],
                    source_item_ref=3663,
                    source_item_uid=actor["id"],
                    generation=generation,
                )
        return account, generation, main, hero, other

    def clock_row(self, identity):
        with self.store.connection() as db:
            return dict(
                db.execute(
                    "SELECT remaining_ms,online_generation,online_anchor_ms FROM character_consumable_buffs WHERE character_id=%s",
                    (identity,),
                ).fetchone()
            )

    def test_inactive_gap_rejoin_and_active_swap_preserve_exact_connected_time(self):
        account, generation, main, hero, _ = self.fixture()
        self.store.clock = lambda: 1002
        heroes.remove(self.store, account, generation, main["id"], hero["id"])
        paused = self.clock_row(hero["id"])
        self.assertEqual(
            (paused["remaining_ms"], paused["online_generation"]), (898000, None)
        )
        self.store.clock = lambda: 1100
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        self.assertEqual(self.clock_row(hero["id"])["remaining_ms"], 898000)
        before_swap = self.clock_row(hero["id"])
        heroes.switch_main(self.store, account, generation, main["id"], hero["id"])
        self.assertEqual(self.clock_row(hero["id"]), before_swap)
        self.store.clock = lambda: 1101
        synchronize(
            self.store, account, generation, self.store.character(account, hero["id"])
        )
        self.assertEqual(self.clock_row(hero["id"])["remaining_ms"], 897000)

    def test_unrelated_main_selection_and_failed_membership_roll_back_clocks(self):
        account, generation, main, hero, other = self.fixture()
        self.store.clock = lambda: 1002
        original = self.clock_row(hero["id"])
        from wakfu_server import consumable_world_lifecycle

        real = consumable_world_lifecycle.company_membership

        def fail_after_clock(*args, **kwargs):
            real(*args, **kwargs)
            raise RuntimeError("membership rollback")

        with patch.object(
            consumable_world_lifecycle, "company_membership", fail_after_clock
        ):
            with self.assertRaisesRegex(RuntimeError, "membership rollback"):
                heroes.remove(self.store, account, generation, main["id"], hero["id"])
        self.assertEqual(self.clock_row(hero["id"]), original)
        with self.store.connection() as db:
            roster = heroes.load_roster(db, self.store, account, main["id"])
        self.assertEqual([row["id"] for row in roster["heroes"]], [hero["id"]])
        self.store.select_character(account, generation, other["id"])
        self.assertEqual(
            (
                self.clock_row(main["id"])["remaining_ms"],
                self.clock_row(main["id"])["online_generation"],
            ),
            (898000, None),
        )
        self.assertEqual(self.clock_row(hero["id"]), original)
        self.store.clock = lambda: 1100
        self.store.select_character(account, generation, main["id"])
        self.assertEqual(self.clock_row(main["id"])["remaining_ms"], 898000)
        self.store.clock = lambda: 1101
        synchronize(
            self.store, account, generation, self.store.character(account, main["id"])
        )
        self.assertEqual(self.clock_row(main["id"])["remaining_ms"], 897000)
