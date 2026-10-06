import struct
import unittest
from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_consumables import use, healing_plan
from wakfu_server import health_store
from wakfu_server import health_policy


class ConsumableTests(PostgresCase):
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
