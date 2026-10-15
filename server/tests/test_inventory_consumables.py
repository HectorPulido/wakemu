import struct
import unittest
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_consumables import use, healing_plan, food_healing_amount
from wakfu_server import health_store
from wakfu_server import health_policy
from wakfu_server.wire import proto_field


class FoodHealingArithmeticTests(unittest.TestCase):
    def character(self):
        sheet = proto_field(24, (1 << 64) - 1).hex()
        equipment = proto_field(10, proto_field(8, 1000) + proto_field(16, 4)).hex()
        return dict(
            id=1,
            breed=8,
            level=6,
            hp=10,
            max_hp=100,
            active_build_index=0,
            inventory_items=[
                dict(uid=1000, character_id=1, reference=2021, quantity=1)
            ],
            builds={
                0: dict(equipment=equipment, sheet=sheet),
                1: dict(equipment="", sheet=sheet),
            },
        )

    def test_real_equipped_mastery_does_not_increase_mask_two_food(self):
        from wakfu_server.equipment_stats import bonuses

        character = self.character()
        self.assertEqual(bonuses(character)["stats"][20], 9)
        self.assertEqual(food_healing_amount(character, 55), 55)

    def test_inactive_equipment_does_not_contribute_or_block(self):
        character = self.character()
        character["active_build_index"] = 1
        # An inactive reference is deliberately unavailable: food evaluation
        # must not validate or read that unselected sheet.
        character["inventory_items"] = []
        self.assertEqual(food_healing_amount(character, 55), 55)

    def test_target_resistance_and_native_fractional_rounding_are_applied(self):
        with patch(
            "wakfu_server.equipment_stats.bonuses",
            return_value={"stats": {32: 100, 18: 900, 20: 900, 114: 500}},
        ):
            # 55 * (1 - 10%) = 49.5. Source mastery/final bonuses are disabled
            # by mask2; target resistance remains enabled.
            self.assertEqual(
                food_healing_amount(self.character(), 55, rng=lambda: 0), 50
            )
            self.assertEqual(
                food_healing_amount(self.character(), 55, rng=lambda: 0.99), 49
            )


class ConsumableTests(PostgresCase):
    def test_equipped_food_and_inactive_build_preserve_gear_and_consume_one(self):
        store = self.store
        account = store.register("equipped-food", "local-password")["id"]
        character = store.create_character(account, "Equipped Food", breed=8)
        generation = store.begin_session(account)
        store.select_character(account, generation, character["id"])
        with store.connection() as db:
            db.execute("UPDATE characters SET level=6 WHERE id=%s", (character["id"],))
        container = character["inventory_containers"][0]["uid"]
        gear = grant(
            store,
            account,
            generation,
            character["id"],
            reference=2021,
            quantity=1,
            container=container,
            slot=0,
            allowed_references={2021},
        )
        food = grant(
            store,
            account,
            generation,
            character["id"],
            reference=3864,
            quantity=2,
            container=container,
            slot=1,
            allowed_references={3864},
        )
        equipment = proto_field(10, proto_field(8, gear["uid"]) + proto_field(16, 4))
        for index in (0, 1):
            sheet = b"".join(
                proto_field(tag, value)
                for tag, value in [(8, index), (18, b"Food gear"), (24, 6), (56, 0)]
            )
            store.save_build(
                account,
                generation,
                character["id"],
                index,
                {"sheet": sheet, "equipment": equipment, "deck": b"", "aptitudes": b""},
            )
        health_store.initialize(store, account, generation, character["id"])
        current = store.character(account, character["id"])
        health_store.sync(
            store, account, generation, character["id"], current["hp"], 10
        )
        result = use(
            store,
            account,
            generation,
            character["id"],
            struct.pack(">qB", food["uid"], 0),
            expected_hp=10,
            in_fight=False,
        )
        self.assertEqual(result["healed"], 55)
        reopened = self.reopen().character(account, character["id"])
        self.assertEqual(reopened["hp"], 65)
        self.assertEqual(reopened["builds"][0]["equipment"], equipment.hex())
        self.assertEqual(reopened["builds"][1]["equipment"], equipment.hex())
        quantities = {
            item["uid"]: item["quantity"] for item in reopened["inventory_items"]
        }
        self.assertEqual(quantities, {gear["uid"]: 1, food["uid"]: 1})

    def test_food_pays_hidden_wounds_and_regeneration_uses_remaining_debt(self):
        store = self.store
        store.clock = lambda: 1.0
        account = store.register("hidden-food", "local-password")["id"]
        char = store.create_character(account, "Hidden Food")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        health_store.initialize(
            store, account, generation, char["id"], coefficient=1, now_ms=1000
        )
        with store.connection() as db:
            character = store.character(account, char["id"], db)
            self.assertEqual(health_policy.apply_damage(db, character, 100, False), 1)
        character = health_store.sync(
            store,
            account,
            generation,
            char["id"],
            1,
            1,
            coefficient=1,
            now_ms=1000,
        )
        item = grant(
            store,
            account,
            generation,
            char["id"],
            reference=3864,
            quantity=1,
            container=char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={3864},
        )
        result = use(
            store,
            account,
            generation,
            char["id"],
            struct.pack(">qB", item["uid"], 0),
            expected_hp=1,
            in_fight=False,
        )
        self.assertEqual((result["healed"], result["character"]["hp"]), (14, 15))
        self.assertEqual(
            result["packets"][1], (12436, struct.pack(">qii", char["id"], 15, 1))
        )
        with store.connection() as db:
            row = db.execute(
                "SELECT hp,hp_damage,health_dead FROM characters WHERE id=%s",
                (char["id"],),
            ).fetchone()
            baseline = db.execute(
                "SELECT initial_hp,initial_damage,started_at,coefficient FROM character_regeneration WHERE character_id=%s",
                (char["id"],),
            ).fetchone()
        self.assertEqual(dict(row), {"hp": 15, "hp_damage": 45, "health_dead": False})
        self.assertEqual((baseline["initial_hp"], baseline["initial_damage"]), (15, 45))

        reopened = self.reopen()
        reopened.clock = store.clock
        restored = health_store.initialize(
            reopened, account, generation, char["id"], coefficient=1, now_ms=2000
        )
        self.assertEqual((restored["hp"], restored["hp_damage"]), (15, 45))
        at_two_seconds = health_store.tick(
            reopened, account, generation, char["id"], 15, now_ms=4000
        )
        self.assertEqual((at_two_seconds["hp"], at_two_seconds["hp_damage"]), (16, 44))
        at_four_seconds = health_store.tick(
            reopened, account, generation, char["id"], 16, now_ms=6000
        )
        self.assertEqual(
            (at_four_seconds["hp"], at_four_seconds["hp_damage"]), (16, 44)
        )
        at_six_seconds = health_store.tick(
            reopened, account, generation, char["id"], 16, now_ms=8000
        )
        self.assertEqual((at_six_seconds["hp"], at_six_seconds["hp_damage"]), (17, 43))
        dead = health_store.sync(
            reopened,
            account,
            generation,
            char["id"],
            17,
            0,
            coefficient=0,
            now_ms=9000,
        )
        self.assertEqual(
            (dead["hp"], dead["health_dead"], dead["hp_damage"]), (0, True, 60)
        )
        reopened_dead = self.reopen()
        reopened_dead.clock = store.clock
        restored_dead = health_store.initialize(
            reopened_dead, account, generation, char["id"], coefficient=1, now_ms=6000
        )
        self.assertEqual((restored_dead["hp"], restored_dead["health_dead"]), (0, True))

    def test_real_native_food_heals_consumes_caps_and_reconnects(self):
        self.assertEqual(healing_plan(3864)["amount"], 55)
        for reference in (2021, 18096, 31005):
            with self.assertRaises(ValueError):
                healing_plan(reference)
        store = self.store
        account = store.register("food-owner", "local-password")["id"]
        char = store.create_character(account, "Food Owner")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        health_store.initialize(store, account, generation, char["id"], coefficient=1)
        health_store.sync(store, account, generation, char["id"], 60, 10, coefficient=1)
        item = grant(
            store,
            account,
            generation,
            char["id"],
            reference=3864,
            quantity=2,
            container=char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={3864},
        )
        body = struct.pack(">qB", item["uid"], 0)
        for options in (
            dict(expected_hp=11, in_fight=False),
            dict(expected_hp=10, in_fight=True),
        ):
            with self.assertRaises(ValueError):
                use(store, account, generation, char["id"], body, **options)
        self.assertEqual(
            store.character(account, char["id"])["inventory_items"][0]["quantity"],
            2,
        )
        result = use(
            store,
            account,
            generation,
            char["id"],
            body,
            expected_hp=10,
            in_fight=False,
        )
        self.assertEqual((result["healed"], result["character"]["hp"]), (50, 60))
        self.assertEqual(
            result["packets"][0], (12470, struct.pack(">qh", item["uid"], -1))
        )
        self.assertEqual(
            result["packets"][1], (12436, struct.pack(">qii", char["id"], 60, 1))
        )
        fresh = self.reopen().character(account, char["id"])
        self.assertEqual(
            (fresh["hp"], fresh["inventory_items"][0]["quantity"]), (60, 1)
        )
        with self.assertRaises(ValueError):
            use(
                store,
                account,
                generation,
                char["id"],
                body,
                expected_hp=60,
                in_fight=False,
            )
        health_store.sync(store, account, generation, char["id"], 60, 1)
        result = use(
            store,
            account,
            generation,
            char["id"],
            body,
            expected_hp=1,
            in_fight=False,
        )
        self.assertEqual(result["character"]["inventory_items"], [])
        self.assertEqual(result["character"]["hp"], 56)

    def test_dead_and_foreign_use_do_not_consume(self):
        store = self.store
        account = store.register("dead-food", "local-password")["id"]
        char = store.create_character(account, "Dead Food")
        other = store.create_character(account, "Other Food")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        item = grant(
            store,
            account,
            generation,
            char["id"],
            reference=3864,
            quantity=1,
            container=char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={3864},
        )
        body = struct.pack(">qB", item["uid"], 0)
        health_store.initialize(store, account, generation, char["id"])
        health_store.sync(store, account, generation, char["id"], 60, 0)
        with self.assertRaises(ValueError):
            use(
                store,
                account,
                generation,
                char["id"],
                body,
                expected_hp=0,
                in_fight=False,
            )
        store.select_character(account, generation, other["id"])
        health_store.initialize(store, account, generation, other["id"])
        health_store.sync(store, account, generation, other["id"], 60, 10)
        with self.assertRaises(ValueError):
            use(
                store,
                account,
                generation,
                other["id"],
                body,
                expected_hp=10,
                in_fight=False,
            )
        self.assertEqual(
            store.character(account, char["id"])["inventory_items"][0]["quantity"],
            1,
        )
