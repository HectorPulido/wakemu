"""Native profession bonuses from their exact active state effects."""
import unittest
from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.profession_store import award
from wakfu_server.consumable_buffs import apply_states
from wakfu_server.profession_consumable_modifiers import aggregate, duration_ms


class ProfessionConsumableModifierTests(unittest.TestCase):
    def test_turbo_craft_and_gathering_bonuses_are_category_specific(self):
        turbo = {"level": 10, "effect_ids": [173761, 173762]}
        values = aggregate([turbo], 64)
        self.assertEqual(values["collect_xp"], 100)
        self.assertEqual(values["craft_xp"], 100)
        self.assertEqual(values["plant_xp"], 0)
        self.assertEqual(values["collect_speed"], 0)

        faster = {"level": 10, "effect_ids": [180993, 180994]}
        values = aggregate([faster], 64)
        self.assertEqual(values["plant_speed"], 50)
        self.assertEqual(values["collect_speed"], 50)
        self.assertEqual(values["craft_speed"], 0)

    def test_profession_scope_and_unknown_battleground_context_fail_closed(self):
        rice = {"level": 15, "effect_ids": [61979]}
        self.assertEqual(aggregate([rice], 64)["collect_quantity"], 15)
        self.assertEqual(aggregate([rice], 65)["collect_quantity"], 0)
        conditional = {"level": 10, "effect_ids": [180990]}
        self.assertEqual(aggregate([conditional], 64)["craft_speed"], 0)
        self.assertEqual(
            aggregate([conditional], 64, is_battleground=False)["craft_speed"], 50
        )
        self.assertEqual(
            aggregate([conditional], 64, is_battleground=True)["craft_speed"], 0
        )

    def test_native_speed_duration_uses_java_rounding(self):
        self.assertEqual(duration_ms(3_000, 50), 2_000)
        self.assertEqual(duration_ms(3_000, 100), 1_500)
        self.assertEqual(duration_ms(3_000, 0), 3_000)
        with self.assertRaises(ValueError):
            duration_ms(3_000, -100)


class ProfessionConsumableAwardPostgresTests(PostgresCase):
    def test_native_food_effects_apply_only_to_matching_profession_xp_category(self):
        account = self.store.register("profession-food", "local-password")["id"]
        character = self.store.create_character(account, "Profession Food")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_professions(account_id,profession_id) VALUES(%s,64)",
                (account,),
            )
            db.execute(
                "UPDATE settings SET value=%s WHERE name='profession_xp'",
                (Jsonb({"multiplier_basis_points": 10_000}),),
            )
        character = self.store.character(account, character["id"])
        source = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=20034,
            quantity=1,
            container=next(
                bag["uid"]
                for bag in character["inventory_containers"]
                if bag["kind"] == 0
            ),
            slot=0,
            allowed_references={20034},
        )
        with self.store.connection() as db:
            apply_states(
                self.store,
                db,
                character["id"],
                [
                    dict(
                        state_id=4073,
                        level=10,
                        clock="online",
                        duration_ms=60_000,
                        stacking="replace",
                        effect_ids=[173761, 173762],
                        removes=[],
                    )
                ],
                source_item_ref=20034,
                source_item_uid=source["uid"],
                generation=generation,
            )
        with self.store.connection() as db:
            harvest = award(
                self.store,
                db,
                account,
                generation,
                character["id"],
                64,
                base_xp=100,
                operation="food-harvest",
                action_category="harvest",
            )
            recipe = award(
                self.store,
                db,
                account,
                generation,
                character["id"],
                64,
                base_xp=100,
                operation="food-recipe",
                action_category="recipe",
            )
            planting = award(
                self.store,
                db,
                account,
                generation,
                character["id"],
                64,
                base_xp=100,
                operation="food-planting",
                action_category="planting",
            )
        self.assertEqual((harvest["xp"], recipe["xp"], planting["xp"]), (200, 200, 100))


if __name__ == "__main__":
    unittest.main()
