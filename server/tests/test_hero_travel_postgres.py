"""Real active owned companions follow main map transitions atomically."""
from postgres_case import PostgresCase
from wakfu_server.characters import heroes


class HeroTravelPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("hero-travel", "travel-password")["id"]
        self.main = self.store.create_character(self.account, "Travel Main")
        self.hero = self.store.create_character(self.account, "Travel Hero")
        self.inactive = self.store.create_character(self.account, "Inactive Hero")
        self.other_account = self.store.register("other-travel", "other-password")["id"]
        self.foreign = self.store.create_character(self.other_account, "Foreign Hero")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])
        heroes.add(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )
        self.destination = dict(map_id=1385, instance_id=0, x=3, y=-21, z=7)

    def test_active_companions_travel_with_main_but_other_characters_do_not(self):
        untouched = {
            c["id"]: tuple(c[k] for k in self.destination)
            for c in (self.inactive, self.foreign)
        }
        moved = self.store.transition_map(
            self.account, self.generation, self.main["id"], self.main, self.destination
        )
        self.assertEqual(self.destination, {k: moved[k] for k in self.destination})
        companion = self.store.character(self.account, self.hero["id"])
        self.assertEqual(self.destination, {k: companion[k] for k in self.destination})
        for old in (self.inactive, self.foreign):
            current = self.store.character(old["account_id"], old["id"])
            self.assertEqual(
                untouched[old["id"]], tuple(current[k] for k in self.destination)
            )

    def test_failed_origin_comparison_does_not_move_companions(self):
        before = self.store.character(self.account, self.hero["id"])
        with self.assertRaises(ValueError):
            self.store.transition_map(
                self.account,
                self.generation,
                self.main["id"],
                dict(self.main, x=self.main["x"] + 1),
                self.destination,
            )
        after = self.store.character(self.account, self.hero["id"])
        self.assertEqual(
            tuple(before[k] for k in self.destination),
            tuple(after[k] for k in self.destination),
        )

    def test_replaced_main_session_does_not_move_companions(self):
        before = self.store.character(self.account, self.hero["id"])
        self.store.begin_session(self.account)
        with self.assertRaises((ValueError, PermissionError)):
            self.store.transition_map(
                self.account,
                self.generation,
                self.main["id"],
                self.main,
                self.destination,
            )
        after = self.store.character(self.account, self.hero["id"])
        self.assertEqual(
            tuple(before[k] for k in self.destination),
            tuple(after[k] for k in self.destination),
        )
