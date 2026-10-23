"""Native known-recipe secret craft lifecycle, using the production APIs."""
import struct
from collections import Counter

from postgres_case import PostgresCase
from wakfu_server import inventory_items, recipe_learning
from wakfu_server.craft_catalog import load_catalog
from wakfu_server.crafting import begin, complete
from wakfu_server.inventory_move import STACKS
from wakfu_server.profession_store import ensure_learned


class SecretRecipeCraftingPostgresTests(PostgresCase):
    def test_native_book_unlocks_amakna_sword_craft_and_replay_is_idempotent(self):
        clock = [1000.0]
        self.store.clock = lambda: clock[0]
        account = self.store.register("secret-recipe-crafter", "local-password")["id"]
        character = self.store.create_character(account, "Secret Recipe Crafter")
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
        recipe = catalog.recipes[7860]
        request = struct.pack(">qii", 31516, 7860, 1)

        with self.assertRaisesRegex(ValueError, "has not been learned"):
            begin(
                self.store,
                catalog,
                account,
                generation,
                character["id"],
                12231,
                request,
                station=station,
            )

        # A second account with the same profession and station cannot borrow
        # account one’s learned-recipe collection.
        other_account = self.store.register(
            "other-secret-recipe-crafter", "local-password"
        )["id"]
        other_character = self.store.create_character(other_account, "Other Crafter")
        other_generation = self.store.begin_session(other_account)
        self.store.select_character(
            other_account, other_generation, other_character["id"]
        )
        ensure_learned(
            self.store, other_account, other_generation, other_character["id"], [83]
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=3000000 WHERE account_id=%s AND profession_id=83",
                (other_account,),
            )
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=0,x=-16,y=6,z=-4 WHERE id=%s",
                (other_character["id"],),
            )
        with self.assertRaisesRegex(ValueError, "has not been learned"):
            begin(
                self.store,
                catalog,
                other_account,
                other_generation,
                other_character["id"],
                12231,
                request,
                station=station,
            )

        # Insert two distinct native books so a post-revocation relock can be
        # exercised without reusing the durable source-UID receipt.
        book_uids = []
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (character["id"],),
            ).fetchone()["uid"]
            for _ in range(2):
                slot = db.execute(
                    "SELECT COALESCE(MAX(slot)+1,0) AS slot FROM inventory_items WHERE container=%s",
                    (bag,),
                ).fetchone()["slot"]
                book_uids.append(
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                        "VALUES(%s,26719,1,%s,%s) RETURNING uid",
                        (character["id"], bag, slot),
                    ).fetchone()["uid"]
                )
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        descriptor = _rules()[26719]
        self.assertEqual(descriptor["use_action_id"], 10910)
        learned = recipe_learning.learn(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">iq", descriptor["use_action_id"], book_uids[0]),
        )
        self.assertTrue(learned["applied"])
        with self.store.connection() as db:
            actions = db.execute(
                "SELECT actions FROM account_professions WHERE account_id=%s AND profession_id=83",
                (account,),
            ).fetchone()["actions"]
        self.assertIn(7860, actions)

        # Revoke the native knowledge between occupation start and finish.
        # Completion must re-evaluate the account criterion without consuming
        # the stored ingredients or producing an output.
        self._grant_ingredients(account, generation, character["id"], recipe)
        before = self.store.character(account, character["id"])
        before_counts = self._counts(before)
        started = begin(
            self.store,
            catalog,
            account,
            generation,
            character["id"],
            12231,
            request,
            station=station,
        )
        clock[0] += started["duration_ms"] / 1000 + 0.01
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET actions='{}'::integer[] WHERE account_id=%s AND profession_id=83",
                (account,),
            )
        with self.assertRaisesRegex(ValueError, "has not been learned"):
            complete(
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
        self.assertEqual(
            before["inventory_items"],
            self.store.character(account, character["id"])["inventory_items"],
        )

        relock = recipe_learning.learn(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">iq", descriptor["use_action_id"], book_uids[1]),
        )
        self.assertTrue(relock["applied"])
        completed = complete(
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
        self.assertFalse(completed["replay"])
        after = self.store.character(account, character["id"])
        expected = before_counts.copy()
        for ingredient in recipe["ingredients"]:
            expected[ingredient["item_id"]] -= ingredient["quantity"]
        for product in recipe["products"]:
            expected[product["item_id"]] += product["quantity"]
        expected[26719] -= 1
        self.assertEqual(+expected, +self._counts(after))
        self.assertEqual(1, self._counts(after)[26495])
        replay = complete(
            self.store,
            catalog,
            account,
            generation,
            character["id"],
            started["token"],
            completed["version"],
            bytes.fromhex("020008"),
            station=station,
        )
        self.assertTrue(replay["replay"])
        self.assertEqual(
            after["inventory_items"],
            self.store.character(account, character["id"])["inventory_items"],
        )
        with self.reopen().connection() as db:
            actions = db.execute(
                "SELECT actions FROM account_professions WHERE account_id=%s AND profession_id=83",
                (account,),
            ).fetchone()["actions"]
        self.assertIn(7860, actions)

    def _grant_ingredients(self, account, generation, character_id, recipe):
        for ingredient in recipe["ingredients"]:
            current = self.store.character(account, character_id)
            bag = current["inventory_containers"][0]
            occupied = {
                item["slot"]
                for item in current["inventory_items"]
                if item["container"] == bag["uid"]
            }
            slot = next(n for n in range(bag["capacity"]) if n not in occupied)
            inventory_items.grant(
                self.store,
                account,
                generation,
                character_id,
                reference=ingredient["item_id"],
                quantity=ingredient["quantity"],
                container=bag["uid"],
                slot=slot,
                allowed_references=set(STACKS),
            )

    @staticmethod
    def _counts(character):
        counts = Counter()
        for item in character["inventory_items"]:
            counts[item["reference"]] += item["quantity"]
        return counts
