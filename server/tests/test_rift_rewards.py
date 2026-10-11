"""Local rift reward policy, draw audit and durable delivery regressions."""
import unittest
from unittest.mock import patch, MagicMock
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


class RiftNativePoolTests(unittest.TestCase):
    def test_native_pool_freezes_only_supported_eligible_physical_items(self):
        p = policy()
        pool = p["pools"][0]
        pool.update(category="item", source="native_rift_monsters", references=[])

        def row(ref, **changes):
            return dict(
                reference_id=ref,
                probability=1,
                is_loot_table=False,
                complex_criteria=False,
                conditions=[],
                native_csF=0,
                **changes
            )

        rows = [row(2021), row(2022), row(2023), row(9727), row(9999)]
        blocked = row(2222)
        blocked["conditions"] = [{"native_enum": "NOT_IN_INFINITE_WAVES", "value": -1}]
        rows.append(blocked)
        complex_row = row(3333)
        complex_row["complex_criteria"] = True
        rows.append(complex_row)
        pp_row = row(4444)
        pp_row["native_csF"] = 1
        rows.append(pp_row)
        db = MagicMock()
        db.execute.side_effect = [
            MagicMock(fetchall=lambda: [{"reference": 2022}]),
            MagicMock(fetchall=lambda: [{"item_ref": 9727}]),
        ]
        with patch(
            "wakfu_server.inventory_move.STACKS",
            {r: 1 for r in (2021, 2022, 2023, 9727, 2222, 3333, 4444)},
        ), patch(
            "wakfu_server.combat_drop_delivery._template_binding",
            side_effect=lambda ref: ("NOT_BOUND", 0, False)
            if ref == 2021
            else ("BOUND_ON_EQUIP_TO_ACCOUNT", 0, False),
        ):
            resolved = rift_rewards.resolve_native_pools(
                db, p, [100], catalog={"monsters": {100: rows}}
            )
        self.assertEqual(resolved["pools"][0]["references"], [2021])
        self.assertEqual(p["pools"][0]["references"], [])
        self.assertEqual(
            rift_rewards.plan(
                resolved,
                dict(outcome="won", completed_waves=1, defeated_monsters=1),
                rng=lambda n: 0,
            )[0]["reference"],
            2021,
        )
        with self.assertRaisesRegex(ValueError, "resolved before drawing"):
            rift_rewards.plan(
                p, dict(outcome="won", completed_waves=1, defeated_monsters=1)
            )

    def test_empty_or_unknown_native_species_fails_before_award(self):
        p = policy()
        p["pools"][0].update(
            category="item", source="native_rift_monsters", references=[]
        )
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        with self.assertRaisesRegex(ValueError, "no native loot catalog"):
            rift_rewards.resolve_native_pools(db, p, [100], catalog={"monsters": {}})
        with self.assertRaisesRegex(ValueError, "no supported eligible items"):
            rift_rewards.resolve_native_pools(
                db, p, [100], catalog={"monsters": {100: []}}
            )

    def test_native_selector_cannot_be_used_for_special_learning_categories(self):
        p = policy()
        p["pools"][0].update(source="native_rift_monsters", references=[])
        with self.assertRaisesRegex(ValueError, "ordinary item category"):
            rift_rewards.validate_policy(p)


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

    def test_default_survival_endpoint_delivers_loot_after_forty_complete_rounds(self):
        from wakfu_server.combat_state import Actor, Fight

        actors = [
            Actor(self.character, 0, (0, 0, 0), 20, 6, 3, 100, 1, self.account, True),
            Actor(-1, 1, (2, 0, 0), 10, 6, 3, 50, 1),
        ]
        fight = Fight(
            self.fight,
            actors,
            {(x, 0, 0) for x in range(3)},
            {0: {(0, 0, 0)}, 1: {(2, 0, 0)}},
        )
        fight.rift_wave_state = dict(
            instance_id=self.run["instance_id"],
            wave=2,
            turn_budget=self.run["policy"]["turn_budget"],
            wave_actor_ids=[-1],
        )
        fight.ready(self.account)
        rounds = self.run["policy"]["turn_budget"]
        self.assertEqual(rounds, 40)
        for round_index in range(rounds):
            fight.end_turn(
                self.account, self.character, fight.actors[self.character].turn_count
            )
            self.assertEqual(fight.phase, "active")
            fight.end_server_turn(-1, fight.turn_id)
            if round_index < rounds - 1:
                self.assertEqual(fight.phase, "active")
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))
        with self.store.connection() as db:
            receipt = rift_runtime.settle(
                db,
                self.run["instance_id"],
                fight.id,
                outcome="won",
                turn=fight.native_timeline_round,
                apply_rewards=lambda connection, run, result: rift_rewards.apply(
                    connection,
                    run,
                    result,
                    store=self.store,
                    eligible_character_ids=[self.character],
                    rng=lambda n: 0,
                ),
            )
            delivery = rift_rewards.delivery(
                db, self.store, self.run["instance_id"], self.character
            )
            self.assertEqual(receipt["outcome"], "won")
            self.assertEqual(
                delivery["loots"],
                [
                    dict(
                        reference=27083,
                        quantity=2,
                        is_purse_loot=False,
                        is_pvp_loot=False,
                    )
                ],
            )
            self.assertEqual(len(delivery["packets"]), 3)
            self.assertEqual(
                db.execute(
                    "SELECT sum(quantity) AS n FROM inventory_items WHERE character_id=%s AND reference=27083",
                    (self.character,),
                ).fetchone()["n"],
                2,
            )

    def test_native_pool_awards_once_with_resolved_references_frozen_in_receipt(self):
        from psycopg.types.json import Jsonb

        p = policy()
        p["pools"][0].update(
            category="item", source="native_rift_monsters", references=[]
        )
        native_row = dict(
            reference_id=2021,
            probability=1,
            is_loot_table=False,
            complex_criteria=False,
            conditions=[],
            native_csF=0,
        )
        catalog = {
            "monsters": {
                ref: [native_row] for ref in self.run["catalog"]["species_refs"]
            }
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='rift_reward_policy'",
                (Jsonb(p),),
            )
            with patch(
                "wakfu_server.combat_drops.native_drop_catalog", return_value=catalog
            ):
                self.award(db)
                self.award(db)
            snapshot = db.execute(
                "SELECT snapshot FROM fight_drop_awards WHERE fight_id=%s AND character_id=%s",
                (self.fight, self.character),
            ).fetchone()["snapshot"]
            self.assertEqual(snapshot["policy"]["pools"][0]["references"], [2021])
            self.assertEqual(
                snapshot["policy"]["pools"][0]["source"], "native_rift_monsters"
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM rift_item_reward_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT sum(quantity) AS n FROM inventory_items WHERE reference=2021"
                ).fetchone()["n"],
                2,
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
