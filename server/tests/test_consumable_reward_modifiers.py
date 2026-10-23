"""Focused native shop factors and durable fractional gathering regressions."""
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
import unittest

from postgres_case import PostgresCase
from wakfu_server import consumable_buffs, resource_collect
from wakfu_server.combat_reward_context import (
    build_context,
    native_shop_consumable_factor,
)
from wakfu_server.combat_drops import (
    DRAW_DENOMINATOR,
    native_shop_drop_factor,
    plan_player_drops,
)
from wakfu_server.profession_consumable_modifiers import collected_quantity
from wakfu_server.reward_policy import xp_amount

import test_combat_drops as drop_fixtures
import test_combat_reward_context as reward_fixtures
import test_resource_harvest_completion as harvest_fixtures


class ConsumableRewardMathTests(unittest.TestCase):
    def test_actual_actor_xp_factor_defaults_to_100_and_preserves_wisdom(self):
        (
            fight,
            character,
            monsters,
            actor,
            _,
        ) = reward_fixtures.CombatRewardContextTests.setup_fight(self, wisdom=50)
        actor.effect_stats.update({118: 100, 119: 100, 33: 60})
        plain = build_context(fight, character, monsters)
        self.assertEqual(plain["winners"][0]["wisdom"], 50)
        self.assertNotIn("shop_consumable_xp_factor", plain["winners"][0])
        actor.effect_stats[118] = 150
        boosted = build_context(fight, character, monsters)
        self.assertEqual(boosted["winners"][0]["wisdom"], 50)
        self.assertEqual(boosted["winners"][0]["shop_consumable_xp_factor"], 150)
        self.assertEqual(native_shop_drop_factor(actor), 100)
        args = dict(
            character_id=character["id"],
            group_xp=10000,
            xp_rate_bp=10000,
            conquest_rate_bp=10000,
        )
        base = xp_amount(context=plain, **args)
        extra = xp_amount(context=boosted, **args)
        # One final integer truncation can differ from multiplying an already
        # truncated baseline by at most one unit.
        self.assertLessEqual(abs(extra - base * 1.5), 1)
        self.assertEqual(actor.effect_stats[36], 50)

    def test_xp_native_factor_zero_and_1000_are_not_wisdom_bonuses(self):
        (
            fight,
            character,
            monsters,
            actor,
            _,
        ) = reward_fixtures.CombatRewardContextTests.setup_fight(self, wisdom=200)
        actor.effect_stats[118] = 100
        plain = build_context(fight, character, monsters)
        args = dict(
            character_id=character["id"],
            group_xp=10000,
            xp_rate_bp=10000,
            conquest_rate_bp=10000,
        )
        base = xp_amount(context=plain, **args)
        for factor, expected_multiplier in ((0, 0), (150, 1.5), (1000, 10)):
            actor.effect_stats[118] = factor
            boosted = build_context(fight, character, monsters)
            self.assertLessEqual(
                abs(xp_amount(context=boosted, **args) - base * expected_multiplier), 10
            )
            self.assertEqual(boosted["winners"][0]["wisdom"], 200)
        for invalid in (True, -1, 1001, 150.0):
            actor.effect_stats[118] = invalid
            with self.assertRaises(ValueError):
                build_context(fight, character, monsters)

    def test_drop_factor_is_separate_from_capped_prospection(self):
        args = dict(
            monsters=[{"actor_id": -11, "reference": 1}],
            character_id=7,
            prospecting_bonus=200,
            can_loot=True,
            fight_context={},
            catalog=drop_fixtures.catalog_for(drop_fixtures.drop_row("0.008")),
        )

        def plan(**changes):
            return plan_player_drops(
                **dict(args, **changes),
                rng=drop_fixtures.Draws(DRAW_DENOMINATOR - 1),
            )[0]

        base = plan()
        explicit = plan(shop_consumable_factor=100)
        extra = plan(shop_consumable_factor=150)
        self.assertEqual(base, explicit)
        self.assertEqual(base.effective_probability, Decimal("0.024"))
        self.assertEqual(extra.effective_probability, Decimal("0.036"))
        self.assertEqual(
            plan(
                prospecting_bonus=300, shop_consumable_factor=150
            ).effective_probability,
            extra.effective_probability,
        )
        self.assertEqual(base.quantity, extra.quantity)
        self.assertEqual(base.success, extra.success)
        actor = SimpleNamespace(effect_stats={33: 200, 119: 150})
        self.assertEqual(native_shop_drop_factor(actor), 150)
        self.assertEqual(actor.effect_stats[33], 200)
        for invalid in (True, -1, 1001, 150.0):
            with self.assertRaises(ValueError):
                plan(shop_consumable_factor=invalid)

    def test_fractional_yield_keeps_both_outcomes_and_stable_operation_draw(self):
        quantities = [
            collected_quantity(1, 50, operation=f"receipt:{i}") for i in range(64)
        ]
        self.assertEqual(set(quantities), {1, 2})
        self.assertEqual(
            quantities,
            [collected_quantity(1, 50, operation=f"receipt:{i}") for i in range(64)],
        )
        self.assertEqual(collected_quantity(2, 50, operation="whole"), 3)
        self.assertEqual(collected_quantity(1, 0, operation="baseline"), 1)
        self.assertEqual(collected_quantity(99, 0, operation="baseline"), 99)


class ConsumableYieldReceiptTests(PostgresCase):
    plant = harvest_fixtures.ResourceHarvestCompletionTests.plant
    ticket = harvest_fixtures.ResourceHarvestCompletionTests.ticket
    advance = harvest_fixtures.ResourceHarvestCompletionTests.advance

    def setUp(self):
        super().setUp()
        self.clock = [1000.0]
        self.store.clock = lambda: self.clock[0]
        self.account = self.store.register("yield-receipt", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Yield Receipt")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        from wakfu_server.profession_store import ensure_learned

        ensure_learned(
            self.store, self.account, self.generation, self.character["id"], [72]
        )
        self.resource = self.plant(9001, stage=3)

    def test_yield_receipt_matches_actual_inventory_and_replay_grants_nothing(self):
        with self.store.connection() as db:
            before = deepcopy(
                db.execute(
                    "SELECT value FROM settings WHERE name='resource_harvest_rewards'"
                ).fetchone()["value"]
            )
            consumable_buffs.apply_states(
                self.store,
                db,
                self.character["id"],
                [
                    dict(
                        state_id=6256,
                        level=1,
                        clock="wall",
                        duration_ms=7200000,
                        stacking="replace",
                        effect_ids=[295739],
                    )
                ],
                source_item_ref=27579,
                source_item_uid=999999,
                generation=self.generation,
            )
        ticket = self.ticket()
        self.advance()
        result = resource_collect.complete(
            self.store, ticket, harvest_fixtures.result_packet()
        )
        self.assertTrue(result["applied"])
        self.assertEqual(result["outcome"]["base_quantity"], before["product_quantity"])
        self.assertEqual(result["outcome"]["consumable_quantity_percent"], 50)
        self.assertIn(result["outcome"]["quantity"], (1, 2))
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT result FROM resource_harvest_receipts WHERE token=%s",
                (ticket["token"],),
            ).fetchone()["result"]
            inventory = db.execute(
                "SELECT SUM(quantity) AS quantity FROM inventory_items WHERE character_id=%s AND reference=%s",
                (self.character["id"], saved["item_reference"]),
            ).fetchone()["quantity"]
            policy = db.execute(
                "SELECT value FROM settings WHERE name='resource_harvest_rewards'"
            ).fetchone()["value"]
        self.assertEqual(saved, result["outcome"])
        self.assertEqual(inventory, saved["quantity"])
        self.assertEqual(policy, before)
        replay = resource_collect.complete(
            self.store, ticket, harvest_fixtures.result_packet()
        )
        self.assertFalse(replay["applied"])
        self.assertEqual(replay["packets"], [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT SUM(quantity) AS quantity FROM inventory_items WHERE character_id=%s AND reference=%s",
                    (self.character["id"], saved["item_reference"]),
                ).fetchone()["quantity"],
                inventory,
            )
