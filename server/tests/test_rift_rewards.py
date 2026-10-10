"""Local rift reward policy, draw audit and durable delivery regressions."""
import unittest
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server import rift_runtime, rift_rewards
from wakfu_server.rift_policy import select_wave


def policy():
    return dict(
        kind="local_dev_items_v1",
        version=1,
        minimum_completed_waves=1,
        minimum_defeated_monsters=1,
        losses="none",
        max_rolls_per_pool=64,
        pools=[
            dict(
                name="shards",
                category="enchantment",
                references=[27083],
                every_waves=1,
                chance_bp=10000,
                quantity_min=2,
                quantity_max=5,
            )
        ],
    )


class RiftRewardPolicyTests(unittest.TestCase):
    def test_actual_cleared_waves_drive_draws_and_all_random_choices_recorded(self):
        result = dict(
            outcome="won", completed_waves=3, defeated_monsters=12, reached_wave=999
        )
        draws = rift_rewards.plan(policy(), result, rng=lambda n: n - 1)
        self.assertEqual(len(draws), 3)
        self.assertEqual(
            draws[0],
            dict(
                pool_index=0,
                attempt=0,
                chance_draw=9999,
                selection_draw=0,
                quantity_draw=3,
                reference=27083,
                success=True,
                quantity=5,
            ),
        )

    def test_loss_zero_progress_and_roll_limit(self):
        p = policy()
        p["max_rolls_per_pool"] = 2
        for outcome, waves, kills in [
            ("lost", 3, 12),
            ("closed", 3, 12),
            ("won", 0, 0),
        ]:
            self.assertEqual(
                rift_rewards.plan(
                    p,
                    dict(
                        outcome=outcome, completed_waves=waves, defeated_monsters=kills
                    ),
                ),
                [],
            )
        self.assertEqual(
            len(
                rift_rewards.plan(
                    p, dict(outcome="won", completed_waves=10, defeated_monsters=40)
                )
            ),
            2,
        )

    def test_invalid_probability_allowlist_and_random_draw_rejected(self):
        for key, value in [
            ("chance_bp", 10001),
            ("references", [-1]),
            ("quantity_min", 0),
        ]:
            p = policy()
            p["pools"][0][key] = value
            with self.assertRaises(ValueError):
                rift_rewards.validate_policy(p)
        with self.assertRaises(ValueError):
            rift_rewards.plan(
                policy(),
                dict(outcome="won", completed_waves=1, defeated_monsters=4),
                rng=lambda n: n,
            )


class RiftRewardPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("rift-loot", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Riftloot")["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character)
        with self.store.connection() as db:
            self.run = rift_runtime.enter(
                db,
                3,
                self.character,
                [self.character],
                seed="reward-test",
                authorize=lambda c, m: True,
            )
            self.fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                (self.fight, self.character, self.account, self.generation),
            )
            rift_runtime.start(db, self.run["instance_id"], self.character, self.fight)
            refs = select_wave(
                self.run["catalog"], self.run["policy"], self.run["seed"], 1
            )
            rift_runtime.bind_wave(
                db, self.run["instance_id"], 1, list(zip([-4, -3, -2, -1], refs))
            )
            rift_runtime.record_wave(
                db, self.run["instance_id"], 1, [-4, -3, -2, -1], turn=2
            )
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (self.fight,)
            )
            self.run = rift_runtime._run(db, self.run["instance_id"])
        self.result = dict(
            outcome="won",
            completed_waves=1,
            defeated_monsters=4,
            reached_wave=2,
            turn=40,
        )

    def award(self, db, **kwargs):
        return rift_rewards.apply(
            db,
            self.run,
            self.result,
            store=self.store,
            eligible_character_ids=[self.character],
            rng=lambda n: 0,
            **kwargs
        )

    def test_award_replay_after_reopen_never_rerolls_or_duplicates(self):
        with self.store.connection() as db:
            self.award(db)
            first = db.execute("SELECT snapshot FROM fight_drop_awards").fetchone()[
                "snapshot"
            ]
            self.assertEqual(first["algorithm"], rift_rewards.ALGORITHM)
            self.assertEqual(
                db.execute(
                    "SELECT sum(quantity) AS q FROM inventory_items WHERE reference=27083"
                ).fetchone()["q"],
                2,
            )
        with self.reopen().connection() as db:
            with patch.object(
                rift_rewards, "plan", side_effect=AssertionError("reroll")
            ):
                self.award(db)
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_drop_awards").fetchone()[
                    "n"
                ],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT sum(quantity) AS q FROM inventory_items WHERE reference=27083"
                ).fetchone()["q"],
                2,
            )
            self.assertEqual(
                len(
                    rift_rewards.delivery(
                        db, self.store, self.run["instance_id"], self.character
                    )["packets"]
                ),
                3,
            )

    def test_full_bags_keep_award_in_native_temporary_inventory(self):
        with self.store.connection() as db:
            bags = db.execute(
                "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s",
                (self.character,),
            ).fetchall()
            for bag in bags:
                for slot in range(bag["capacity"]):
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,2021,1,%s,%s)",
                        (self.character, bag["uid"], slot),
                    )
            self.award(db)
            self.award(db)
            row = db.execute(
                "SELECT reference,quantity FROM temporary_combat_items"
            ).fetchone()
            self.assertEqual(row, dict(reference=27083, quantity=2))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_drop_delivery_receipts"
                ).fetchone()["n"],
                1,
            )

    def test_delivery_failure_rolls_back_draws_ownership_and_receipts(self):
        with self.assertRaisesRegex(RuntimeError, "delivery failure"):
            with self.store.connection() as db:
                self.award(db)
                raise RuntimeError("delivery failure")
        with self.store.connection() as db:
            for table in (
                "rift_item_reward_receipts",
                "fight_drop_awards",
                "fight_drop_delivery_receipts",
                "inventory_items",
            ):
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"], 0
                )

    def test_invalid_virtual_bonus_spectator_and_early_survival_rejected(self):
        from psycopg.types.json import Jsonb

        with self.store.connection() as db:
            with self.assertRaisesRegex(ValueError, "outside frozen"):
                rift_rewards.apply(
                    db,
                    self.run,
                    self.result,
                    store=self.store,
                    eligible_character_ids=[self.character + 1],
                )
            early = {**self.result, "turn": 39}
            with self.assertRaisesRegex(ValueError, "survival"):
                rift_rewards.apply(
                    db,
                    self.run,
                    early,
                    store=self.store,
                    eligible_character_ids=[self.character],
                )
            p = policy()
            p["pools"][0]["references"] = [27094]
            db.execute(
                "UPDATE settings SET value=%s WHERE name='rift_reward_policy'",
                (Jsonb(p),),
            )
            with self.assertRaisesRegex(ValueError, "Virtual socket"):
                self.award(db)

    def test_appearance_is_bound_physical_item_and_is_not_auto_learned(self):
        from psycopg.types.json import Jsonb

        p = policy()
        p["pools"][0].update(
            name="costume",
            category="appearance",
            references=[9727],
            quantity_min=1,
            quantity_max=1,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='rift_reward_policy'",
                (Jsonb(p),),
            )
            self.award(db)
            item = db.execute(
                "SELECT uid,reference,quantity FROM inventory_items"
            ).fetchone()
            self.assertEqual((item["reference"], item["quantity"]), (9727, 1))
            self.assertTrue(
                db.execute(
                    "SELECT bound FROM inventory_item_bindings WHERE uid=%s",
                    (item["uid"],),
                ).fetchone()["bound"]
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM cosmetic_learning_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_full_default_pool_settles_once_with_sublimation_and_learnable_costume(
        self,
    ):
        with self.store.connection() as db:
            for wave in range(2, 6):
                refs = select_wave(
                    self.run["catalog"], self.run["policy"], self.run["seed"], wave
                )
                ids = [-(wave * 10 + i) for i in range(4)]
                rift_runtime.bind_wave(
                    db, self.run["instance_id"], wave, list(zip(ids, refs))
                )
                rift_runtime.record_wave(
                    db, self.run["instance_id"], wave, ids, turn=wave
                )
            callback = lambda connection, run, result: rift_rewards.apply(
                connection,
                run,
                result,
                store=self.store,
                eligible_character_ids=[self.character],
                rng=lambda n: 0,
            )
            first = rift_runtime.settle(
                db,
                self.run["instance_id"],
                self.fight,
                outcome="won",
                turn=40,
                apply_rewards=callback,
            )
            again = rift_runtime.settle(
                db,
                self.run["instance_id"],
                self.fight,
                outcome="won",
                turn=40,
                apply_rewards=lambda *args: self.fail("reroll"),
            )
            self.assertEqual(first, again)
            refs = {
                r["reference"]
                for r in db.execute("SELECT reference FROM inventory_items").fetchall()
            }
            self.assertTrue({2021, 27083, 27111, 9727} <= refs)
            costume = db.execute(
                "SELECT uid FROM inventory_items WHERE reference=9727"
            ).fetchone()["uid"]
            action = db.execute(
                "SELECT action_id FROM native_cosmetic_learning_actions WHERE item_ref=9727"
            ).fetchone()["action_id"]
        import struct
        from wakfu_server.cosmetic_learning import learn_item

        learned = learn_item(
            self.store,
            self.account,
            self.generation,
            self.character,
            struct.pack(">iq", action, costume),
        )
        self.assertTrue(learned["applied"])
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_items WHERE uid=%s", (costume,)
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM cosmetic_learning_receipts"
                ).fetchone()["n"],
                1,
            )
