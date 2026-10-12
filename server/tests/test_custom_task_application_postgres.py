"""Actual Store leases and selected heroes gate in-game custom list publication."""
from postgres_case import PostgresCase
from wakfu_server.custom_tasks import application, presentation, service


class CustomTaskApplicationPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("task-list-owner", "local-password")["id"]
        self.main = self.store.create_character(self.account, "Task List Main")["id"]
        self.hero = self.store.create_character(self.account, "Task List Hero")["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main)
        with self.store.connection() as db:
            service.settle(
                db,
                self.account,
                self.main,
                "fight:1",
                {
                    "kind": "original_monster_killed",
                    "fight_id": 1,
                    "actors": [{"actor_id": -1, "reference": 1}],
                },
            )

    def publish(self, account=None, generation=None, character=None, gifts=()):
        return application.publication(
            self.store,
            self.account if account is None else account,
            self.generation if generation is None else generation,
            self.main if character is None else character,
            existing_packages=gifts,
            cap_reached=False,
        )

    def test_actual_owned_selected_publication_preserves_genuine_gift_and_progress(
        self,
    ):
        gift = presentation.GiftPackage(
            "Earned gift", "Keep me", (presentation.GiftItem("earned:1", 12686, 2),)
        )
        packet = self.publish(gifts=(gift,))
        self.assertEqual(packet[0], 13369)
        self.assertEqual(packet[1][:2], b"\0\3")
        self.assertIn(b"In progress: 1/20", packet[1])
        self.assertIn(b"earned:1", packet[1])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_events"
                ).fetchone()["n"],
                1,
            )

    def test_foreign_stale_expired_and_unselected_hero_rejected(self):
        foreign = self.store.register("task-list-foreign", "local-password")["id"]
        foreign_generation = self.store.begin_session(foreign)
        for kwargs in (
            {"account": foreign, "generation": foreign_generation},
            {"generation": foreign_generation},
            {"character": self.hero},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.publish(**kwargs)
        newer = self.store.begin_session(self.account)
        self.store.select_character(self.account, newer, self.main)
        with self.assertRaises(ValueError):
            self.publish()
        self.generation = newer
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE account_id=%s",
                (self.account,),
            )
        with self.assertRaises(ValueError):
            self.publish()

    def test_selected_hero_refresh_never_publishes_main_character_counters(self):
        self.store.select_character(self.account, self.generation, self.hero)
        with self.assertRaises(ValueError):
            self.publish(character=self.main)
        hero_packet = self.publish(character=self.hero)
        self.assertIn(b"In progress: 0/20", hero_packet[1])
        self.assertNotIn(b"In progress: 1/20", hero_packet[1])
        self.store.select_character(self.account, self.generation, self.main)
        main_packet = self.publish(character=self.main)
        self.assertIn(b"In progress: 1/20", main_packet[1])
