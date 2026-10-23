"""Craft products must not inherit a resident random-box cursor UID."""
from postgres_case import PostgresCase
from wakfu_server.craft_catalog import load_catalog
from wakfu_server.crafting import _apply_inventory, _plan
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_move import STACKS


class CraftRandomCursorPostgresTests(PostgresCase):
    def test_native_recipe_7193_keeps_used_box_separate_and_preserves_cursor(self):
        account = self.store.register("craft-random-cursor", "local-password")["id"]
        character = self.store.create_character(account, "Craft Random Cursor")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        catalog = load_catalog()
        recipe = catalog.recipes[7193]
        self.assertEqual(81, recipe["profession_id"])
        self.assertEqual(
            [(31740, 1)],
            [(row["item_id"], row["quantity"]) for row in recipe["products"]],
        )

        def add(reference, quantity):
            current = self.store.character(account, character["id"])
            bag = next(
                row for row in current["inventory_containers"] if row["kind"] == 0
            )
            occupied = {
                row["slot"]
                for row in current["inventory_items"]
                if row["container"] == bag["uid"]
            }
            slot = next(
                value for value in range(bag["capacity"]) if value not in occupied
            )
            return grant(
                self.store,
                account,
                generation,
                character["id"],
                reference=reference,
                quantity=quantity,
                container=bag["uid"],
                slot=slot,
                allowed_references=set(STACKS),
            )

        for ingredient in recipe["ingredients"]:
            add(ingredient["item_id"], ingredient["quantity"])
        resident = add(31740, 2)

        with self.store.connection() as db:
            plain_character, plain_plan = _plan(
                self.store,
                db,
                account,
                character["id"],
                catalog.recipes,
                recipe,
                1,
            )
            self.assertEqual(
                resident["uid"], plain_plan["product_placements"][0]["merge_uid"]
            )
            db.execute(
                "INSERT INTO random_item_use_counters(source_uid,next_use) VALUES(%s,8)",
                (resident["uid"],),
            )
            used_character, marked_plan = _plan(
                self.store,
                db,
                account,
                character["id"],
                catalog.recipes,
                recipe,
                1,
            )
            self.assertIsNone(marked_plan["product_placements"][0]["merge_uid"])
            self.assertEqual(
                2,
                next(
                    row["quantity"]
                    for row in marked_plan["final_items"]
                    if row["uid"] == resident["uid"]
                ),
            )
            packets = _apply_inventory(db, character["id"], used_character, marked_plan)
            self.assertTrue(any(opcode == 12471 for opcode, _ in packets))

        after = self.store.character(account, character["id"])
        products = [
            row for row in after["inventory_items"] if row["reference"] == 31740
        ]
        self.assertEqual(2, len(products))
        self.assertEqual(
            2,
            next(row["quantity"] for row in products if row["uid"] == resident["uid"]),
        )
        new_uid = next(row["uid"] for row in products if row["uid"] != resident["uid"])
        self.assertEqual(
            1, next(row["quantity"] for row in products if row["uid"] == new_uid)
        )
        with self.store.connection() as db:
            self.assertEqual(
                8,
                db.execute(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (resident["uid"],),
                ).fetchone()["next_use"],
            )
            self.assertIsNone(
                db.execute(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (new_uid,),
                ).fetchone()
            )
