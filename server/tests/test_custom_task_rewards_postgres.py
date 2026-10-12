"""Private future delivery gates; real isolated Store and native grant helpers."""
import copy
from concurrent.futures import ThreadPoolExecutor
from postgres_case import PostgresCase
from wakfu_server.custom_tasks import service, reward_delivery
from wakfu_server.achievements import rewards


class CustomTaskRewardsPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("custom-reward-owner", "local-password")[
            "id"
        ]
        self.character = self.store.create_character(
            self.account, "Custom Reward Owner"
        )["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character)

    def earn(self, reward_rows):
        definition = dict(
            key="explicit-test-task",
            title="Test task",
            description="One original kill",
            target=1,
            enabled=True,
            predicate=dict(kind="original_monster_killed", references=[1]),
            rewards=copy.deepcopy(reward_rows),
        )
        event = dict(
            kind="original_monster_killed",
            fight_id=1,
            actors=[dict(actor_id=-1, reference=1)],
        )
        with self.store.connection() as db:
            result = service.settle(
                db, self.account, self.character, "fight:1", event, [definition]
            )
            self.assertEqual(result["completed"], ["explicit-test-task"])

    def drain(self, **kwargs):
        return reward_delivery.deliver(
            self.store,
            kwargs.get("account_id", self.account),
            kwargs.get("generation", self.generation),
            kwargs.get("character_id", self.character),
        )

    def test_real_item_reward_once_and_reconnect(self):
        self.earn([dict(aeV=5, ckl=[2021, 1])])
        result = self.drain()
        self.assertEqual(result["delivered"], [("explicit-test-task", 0)])
        self.assertEqual([op for op, _ in result["packets"]], [12471])
        self.assertEqual(len(result["character"]["inventory_items"]), 1)
        self.assertEqual(self.drain()["packets"], [])
        restored = self.reopen().character(self.account, self.character)
        self.assertEqual(len(restored["inventory_items"]), 1)

    def test_capacity_retains_entitlement_then_retry(self):
        self.earn([dict(aeV=5, ckl=[2021, 1])])
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_containers SET capacity=1 WHERE character_id=%s AND kind=0",
                (self.character,),
            )
            rewards.grant(
                db,
                self.store,
                self.store.character(self.account, self.character, db),
                dict(aeV=5, ckl=[2021, 1]),
            )
        blocked = self.drain()
        self.assertEqual(blocked["delivered"], [])
        self.assertEqual(blocked["capacity_pending"], [("explicit-test-task", 0)])
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT delivered_at FROM character_custom_task_reward_outbox"
                ).fetchone()["delivered_at"]
            )
            db.execute(
                "UPDATE inventory_containers SET capacity=2 WHERE character_id=%s AND kind=0",
                (self.character,),
            )
        self.assertEqual(self.drain()["delivered"], [("explicit-test-task", 0)])
        self.assertEqual(self.drain()["packets"], [])

    def test_stale_foreign_deleted_and_incomplete_entitlements_do_not_grant(self):
        self.earn([dict(aeV=5, ckl=[2021, 1])])
        with self.assertRaises(ValueError):
            self.drain(generation="invalid-session")
        foreign = self.store.register("custom-reward-foreign", "local-password")["id"]
        with self.assertRaises(ValueError):
            self.drain(account_id=foreign)
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_custom_task_progress SET completed_at=NULL WHERE character_id=%s",
                (self.character,),
            )
        self.assertEqual(self.drain()["packets"], [])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET deleted_at=CURRENT_TIMESTAMP WHERE id=%s",
                (self.character,),
            )
        with self.assertRaises(ValueError):
            self.drain()

    def test_invalid_reward_rolls_back_prior_grant_and_receipt(self):
        self.earn([dict(aeV=5, ckl=[2021, 1]), dict(aeV=5, ckl=[2021, 1])])
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_custom_task_reward_outbox SET payload='{"
                + '"aeV":17,"ckl":[1]}'
                + "'::jsonb WHERE reward_index=1"
            )
        with self.assertRaises(ValueError):
            self.drain()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM inventory_items WHERE character_id=%s",
                    (self.character,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM character_custom_task_reward_outbox WHERE delivered_at IS NOT NULL"
                ).fetchone()["n"],
                0,
            )

    def test_concurrent_delivery_serializes_once(self):
        self.earn([dict(aeV=5, ckl=[2021, 1])])
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.drain(), range(2)))
        self.assertEqual(sum(len(r["delivered"]) for r in results), 1)
        self.assertEqual(sum(len(r["packets"]) for r in results), 1)
        self.assertEqual(
            len(self.store.character(self.account, self.character)["inventory_items"]),
            1,
        )

    def test_fixed_xp_and_account_unlocks_reload_current_character(self):
        with self.store.connection() as db:
            emote = db.execute(
                "SELECT emote_id FROM native_emote_definitions ORDER BY emote_id LIMIT 1"
            ).fetchone()["emote_id"]
            initial = db.execute(
                "SELECT xp FROM character_progression WHERE character_id=%s",
                (self.character,),
            ).fetchone()["xp"]
        self.earn(
            [dict(aeV=6, ckl=[1000]), dict(aeV=2, ckl=[761]), dict(aeV=3, ckl=[emote])]
        )
        result = self.drain()
        self.assertEqual(len(result["delivered"]), 3)
        self.assertIn(13613, [op for op, _ in result["packets"]])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (self.character,),
                ).fetchone()["xp"],
                initial + 1000,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM account_emote_knowledge WHERE account_id=%s AND emote_id=%s",
                    (self.account, emote),
                ).fetchone()["n"],
                1,
            )
        self.assertEqual(self.drain()["packets"], [])
        self.assertEqual(
            self.reopen().character(self.account, self.character)["level"],
            result["character"]["level"],
        )

    def test_active_fight_rejects_separate_postgame_delivery(self):
        self.earn([dict(aeV=5, ckl=[2021, 1])])
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES('active','pve') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight, self.character, self.account),
            )
        with self.assertRaisesRegex(ValueError, "post-game"):
            self.drain()
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT delivered_at FROM character_custom_task_reward_outbox"
                ).fetchone()["delivered_at"]
            )
