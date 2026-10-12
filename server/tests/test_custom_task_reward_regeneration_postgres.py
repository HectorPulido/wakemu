"""Actual fixed-XP delivery and the actual main closure restore world regeneration."""
import test_custom_task_reward_publication as closure_tests
from postgres_case import PostgresCase
from wakfu_server.custom_tasks import service, reward_delivery
from wakfu_server import health_store
from wakfu_server.progression import XP_BY_LEVEL


class CustomRewardRegenerationPostgresTests(PostgresCase):
    def test_actual_level_crossing_delivery_pauses_then_main_resumes_regeneration(self):
        account = self.store.register("reward-regen-owner", "local-password")["id"]
        character = self.store.create_character(account, "Reward Regen Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        character = health_store.initialize(
            self.store, account, generation, character["id"], coefficient=1
        )
        definition = dict(
            key="regen-level-test",
            title="Hunter",
            description="One original kill",
            target=1,
            enabled=True,
            predicate=dict(kind="original_monster_killed", references=[1]),
            rewards=[dict(aeV=6, ckl=[XP_BY_LEVEL[5]])],
        )
        with self.store.connection() as db:
            service.settle(
                db,
                account,
                character["id"],
                "fight:1",
                dict(
                    kind="original_monster_killed",
                    fight_id=1,
                    actors=[dict(actor_id=-1, reference=1)],
                ),
                [definition],
            )
        actual_delivery = reward_delivery.deliver
        boundary = closure_tests.CustomTaskRewardPublicationTests(
            "test_live_delta_precedes_owned_level_spellbook_and_absolute_inventory"
        )
        boundary.setUp()
        self.addCleanup(boundary.doCleanups)
        boundary.context.update(
            STORE=self.store,
            account_id=account,
            generation=generation,
            health_store=health_store,
        )
        boundary.call, boundary.current = boundary.context["capture"](character)
        paused = []

        def deliver(*args):
            result = actual_delivery(*args)
            with self.store.connection() as db:
                paused.append(
                    db.execute(
                        "SELECT coefficient FROM character_regeneration WHERE character_id=%s",
                        (character["id"],),
                    ).fetchone()["coefficient"]
                )
            return result

        boundary.deliver.side_effect = deliver
        boundary.call()
        self.assertEqual(paused, [0])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT coefficient FROM character_regeneration WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["coefficient"],
                1,
            )
        self.assertGreaterEqual(boundary.current()["level"], 5)
        self.assertEqual(boundary.current()["xp"], character["xp"] + XP_BY_LEVEL[5])
        self.assertEqual(boundary.events[0][0], 13613)
        self.assertEqual(
            [op for op, _ in boundary.events[1:]], [15548, 23548, 13046, 13713]
        )
        count = len(boundary.events)
        boundary.call()
        self.assertEqual(len(boundary.events), count)
        self.assertEqual(boundary.current()["xp"], character["xp"] + XP_BY_LEVEL[5])
