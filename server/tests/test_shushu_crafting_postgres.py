"""Actual native Shushu upgrade recipes through owned crafting transactions."""
import struct
from collections import Counter

from postgres_case import PostgresCase
from wakfu_server import inventory_items
from wakfu_server.craft_catalog import load_catalog
from wakfu_server.crafting import begin, complete
from wakfu_server.inventory_move import STACKS
from wakfu_server.profession_store import ensure_learned


class ShushuCraftingPostgresTests(PostgresCase):
    def test_native_upgrade_recipes_complete_and_secret_recipe_stays_guarded(self):
        clock = [1000.0]
        self.store.clock = lambda: clock[0]
        account = self.store.register("shushu-crafter", "local-password")["id"]
        character = self.store.create_character(account, "Shushu Crafter")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        catalog = load_catalog()
        ensure_learned(self.store, account, generation, character["id"], [83])
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=3000000 WHERE account_id=%s AND profession_id=83",
                (account,),
            )
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=0,x=-16,y=6,z=-4 WHERE id=%s",
                (character["id"],),
            )
        station = dict(
            table_uid=31516,
            map_id=1134,
            instance_id=0,
            definition_id=182,
            profession_id=83,
            in_range=True,
        )
        # Ten 150->155 upgrades, three 230->230 upgrades, the ordinary
        # Trinchafab'huritus recipe, and the derived ancestral-shovel recipe.
        recipes = (
            3573,
            3574,
            3575,
            3576,
            3577,
            3578,
            3579,
            3580,
            3581,
            3582,
            8922,
            8925,
            8929,
            5829,
            9854,
        )
        for recipe_id in recipes:
            with self.subTest(recipe_id=recipe_id):
                recipe = catalog.recipes[recipe_id]
                for ingredient in recipe["ingredients"]:
                    current = self.store.character(account, character["id"])
                    bag = current["inventory_containers"][0]
                    occupied = {
                        i["slot"]
                        for i in current["inventory_items"]
                        if i["container"] == bag["uid"]
                    }
                    slot = next(n for n in range(bag["capacity"]) if n not in occupied)
                    inventory_items.grant(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        reference=ingredient["item_id"],
                        quantity=ingredient["quantity"],
                        container=bag["uid"],
                        slot=slot,
                        allowed_references=set(STACKS),
                    )
                before = self.store.character(account, character["id"])
                before_counts = Counter()
                for item in before["inventory_items"]:
                    before_counts[item["reference"]] += item["quantity"]
                started = begin(
                    self.store,
                    catalog,
                    account,
                    generation,
                    character["id"],
                    12231,
                    struct.pack(">qii", 31516, recipe_id, 1),
                    station=station,
                )
                clock[0] += started["duration_ms"] / 1000 + 0.01
                outcome = complete(
                    self.store,
                    catalog,
                    account,
                    generation,
                    character["id"],
                    started["token"],
                    started["version"],
                    bytes.fromhex("020008"),
                    station=station,
                )
                self.assertFalse(outcome["replay"])
                expected = before_counts.copy()
                for item in recipe["ingredients"]:
                    expected[item["item_id"]] -= item["quantity"]
                for item in recipe["products"]:
                    expected[item["item_id"]] += item["quantity"]
                after = self.store.character(account, character["id"])
                actual = Counter()
                for item in after["inventory_items"]:
                    actual[item["reference"]] += item["quantity"]
                self.assertEqual(+expected, +actual)
                replay = complete(
                    self.store,
                    catalog,
                    account,
                    generation,
                    character["id"],
                    started["token"],
                    outcome["version"],
                    bytes.fromhex("020008"),
                    station=station,
                )
                self.assertTrue(replay["replay"])
        # The native secret recipe still requires account knowledge even
        # though the ordinary upgrade matrix above needs no recipe book.
        before = self.store.character(account, character["id"])
        with self.assertRaisesRegex(ValueError, "has not been learned"):
            begin(
                self.store,
                catalog,
                account,
                generation,
                character["id"],
                12231,
                struct.pack(">qii", 31516, 7860, 1),
                station=station,
            )
        self.assertEqual(
            before["inventory_items"],
            self.store.character(account, character["id"])["inventory_items"],
        )
