"""Actual native precursor crafting with lossless per-unit output state."""
import struct
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import crafting, inventory_items
from wakfu_server.craft_catalog import load_catalog
from wakfu_server.inventory_move import STACKS
from wakfu_server.profession_store import ensure_learned


class CraftUpgradePolicyPostgresTests(PostgresCase):
    def fixture(self):
        self.clock = [1000.0]
        self.store.clock = lambda: self.clock[0]
        account = self.store.register("rich-upgrade-crafter", "local-password")["id"]
        character = self.store.create_character(account, "Upgrade Crafter")
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
        return account, generation, character, catalog, station

    def give(self, account, generation, character, reference, quantity=1):
        current = self.store.character(account, character["id"])
        bag = current["inventory_containers"][0]
        occupied = {
            row["slot"]
            for row in current["inventory_items"]
            if row["container"] == bag["uid"]
        }
        slot = next(slot for slot in range(bag["capacity"]) if slot not in occupied)
        return inventory_items.grant(
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

    def ingredients(self, account, generation, character, recipe):
        from wakfu_server.element_selection import select, _required_counts

        source = None
        for ingredient in recipe["ingredients"]:
            item = self.give(
                account,
                generation,
                character,
                ingredient["item_id"],
                ingredient["quantity"],
            )
            if ingredient["item_id"] == recipe["raw_cvj"]:
                source = item
        self.assertIsNotNone(source)
        counts = _required_counts(source["reference"])
        masks = [
            sum(1 << (i + 1) for i in range(counts[key]))
            for key in ("damage_elements", "resistance_elements")
        ]
        select(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qBB", source["uid"], *masks),
        )
        with self.store.connection() as db:
            state = bytes(
                db.execute(
                    "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["shard_state"]
            )
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,true,%s) ON CONFLICT(uid) DO UPDATE SET bound=true",
                (source["uid"], source["reference"]),
            )
        return source, masks, state

    def start(self, account, generation, character, catalog, station, recipe_id):
        return crafting.begin(
            self.store,
            catalog,
            account,
            generation,
            character["id"],
            12231,
            struct.pack(">qii", 31516, recipe_id, 1),
            station=station,
        )

    def finish(self, account, generation, character, catalog, station, started):
        self.clock[0] += started["duration_ms"] / 1000 + 0.01
        return crafting.complete(
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

    def test_native_precursor_upgrade_preserves_identified_sockets_binding_replay_and_reload(
        self,
    ):
        account, generation, character, catalog, station = self.fixture()
        recipe = catalog.recipes[3575]
        source, masks, blob = self.ingredients(account, generation, character, recipe)
        target = recipe["products"][0]["item_id"]
        resident = self.give(account, generation, character, target)
        started = self.start(account, generation, character, catalog, station, 3575)
        outcome = self.finish(account, generation, character, catalog, station, started)
        current = self.store.character(account, character["id"])
        products = [
            row
            for row in current["inventory_items"]
            if row["reference"] == target and row["uid"] != resident["uid"]
        ]
        self.assertEqual(
            len(products),
            1,
            "A rich precursor must produce one fresh nonmerged output identity",
        )
        main = products[0]
        self.assertNotEqual(main["uid"], source["uid"])
        self.assertEqual(
            (main["damage_elements"], main["resistance_elements"]), tuple(masks)
        )
        self.assertEqual(main["shard_state"], blob)
        self.assertEqual(
            next(
                row
                for row in current["inventory_items"]
                if row["uid"] == resident["uid"]
            )["quantity"],
            1,
        )
        with self.store.connection() as db:
            self.assertTrue(
                db.execute(
                    "SELECT bound FROM inventory_item_bindings WHERE uid=%s",
                    (main["uid"],),
                ).fetchone()["bound"]
            )
        replay = crafting.complete(
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
        self.assertEqual(
            current["inventory_items"],
            self.reopen().character(account, character["id"])["inventory_items"],
        )

    def test_compatible_nullable_recycling_observation_survives_native_upgrade(self):
        account, generation, character, catalog, station = self.fixture()
        recipe = catalog.recipes[3575]
        source, _, blob = self.ingredients(account, generation, character, recipe)
        observation = dict(unidentified=None, socketed=True)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) VALUES(%s,%s,%s)",
                (source["uid"], observation["unidentified"], observation["socketed"]),
            )
        started = self.start(account, generation, character, catalog, station, 3575)
        outcome = self.finish(account, generation, character, catalog, station, started)
        current = self.store.character(account, character["id"])
        main = next(
            row for row in current["inventory_items"] if row["reference"] == 18450
        )
        self.assertNotEqual(main["uid"], source["uid"])
        self.assertEqual(main["shard_state"], blob)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT unidentified,socketed FROM inventory_item_recycling_state WHERE uid=%s",
                    (main["uid"],),
                ).fetchone(),
                observation,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_item_recycling_state WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()
            )
        replay = crafting.complete(
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
        reopened = self.reopen()
        self.assertEqual(
            current["inventory_items"],
            reopened.character(account, character["id"])["inventory_items"],
        )
        with reopened.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT unidentified,socketed FROM inventory_item_recycling_state WHERE uid=%s",
                    (main["uid"],),
                ).fetchone(),
                observation,
            )

    def test_unsupported_rich_ingredient_and_changed_precursor_leave_all_materials_intact(
        self,
    ):
        from wakfu_server.wire import proto_field

        account, generation, character, catalog, station = self.fixture()
        recipe = catalog.recipes[3575]
        source, masks, blob = self.ingredients(account, generation, character, recipe)
        with self.store.connection() as db:
            before = list(
                db.execute(
                    "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                    (character["id"],),
                )
            )
            db.execute(
                "UPDATE inventory_item_shards SET shard_state=%s WHERE uid=%s",
                (blob + proto_field(800, 1), source["uid"]),
            )
        with self.assertRaises(ValueError):
            self.start(account, generation, character, catalog, station, 3575)
        with self.store.connection() as db:
            self.assertEqual(
                before,
                list(
                    db.execute(
                        "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                        (character["id"],),
                    )
                ),
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM craft_occupations WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()
            )
            db.execute(
                "UPDATE inventory_item_shards SET shard_state=%s WHERE uid=%s",
                (blob, source["uid"]),
            )
        started = self.start(account, generation, character, catalog, station, 3575)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_item_shards SET shard_state=%s WHERE uid=%s",
                (blob + proto_field(72, 3), source["uid"]),
            )
        with self.assertRaises(ValueError):
            self.finish(account, generation, character, catalog, station, started)
        with self.store.connection() as db:
            self.assertEqual(
                before,
                list(
                    db.execute(
                        "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                        (character["id"],),
                    )
                ),
            )
            db.execute(
                "UPDATE inventory_item_shards SET shard_state=%s WHERE uid=%s",
                (blob, source["uid"]),
            )
        with patch(
            "wakfu_server.craft_upgrade_policy.apply",
            side_effect=ValueError("injected provider failure"),
        ):
            with self.assertRaises(ValueError):
                self.finish(account, generation, character, catalog, station, started)
        with self.store.connection() as db:
            self.assertEqual(
                before,
                list(
                    db.execute(
                        "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                        (character["id"],),
                    )
                ),
            )
            self.assertEqual(
                bytes(
                    db.execute(
                        "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                        (source["uid"],),
                    ).fetchone()["shard_state"]
                ),
                blob,
            )

    def test_batch_preserves_each_rich_precursor_as_its_own_fresh_output(self):
        from wakfu_server.element_selection import select, _required_counts

        account, generation, character, catalog, station = self.fixture()
        recipe = catalog.recipes[3575]
        sources = []
        for ingredient in recipe["ingredients"]:
            if ingredient["item_id"] == recipe["raw_cvj"]:
                sources = [
                    self.give(account, generation, character, ingredient["item_id"])
                    for _ in range(2)
                ]
            else:
                self.give(
                    account,
                    generation,
                    character,
                    ingredient["item_id"],
                    ingredient["quantity"] * 2,
                )
        expected = []
        counts = _required_counts(recipe["raw_cvj"])
        for index, source in enumerate(sources):
            masks = [
                sum(1 << (((i + index) % 4) + 1) for i in range(counts[key]))
                for key in ("damage_elements", "resistance_elements")
            ]
            select(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">qBB", source["uid"], *masks),
            )
            with self.store.connection() as db:
                blob = bytes(
                    db.execute(
                        "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                        (source["uid"],),
                    ).fetchone()["shard_state"]
                )
            expected.append((masks[0], masks[1], blob))
        target = recipe["products"][0]["item_id"]
        resident = self.give(account, generation, character, target)
        started = crafting.begin(
            self.store,
            catalog,
            account,
            generation,
            character["id"],
            12231,
            struct.pack(">qii", 31516, 3575, 2),
            station=station,
        )
        outcome = self.finish(account, generation, character, catalog, station, started)
        current = self.store.character(account, character["id"])
        products = [
            row
            for row in current["inventory_items"]
            if row["reference"] == target and row["uid"] != resident["uid"]
        ]
        self.assertEqual(len(products), 2)
        self.assertEqual(len({row["uid"] for row in products}), 2)
        self.assertTrue(
            {row["uid"] for row in products}.isdisjoint(
                source["uid"] for source in sources
            )
        )
        self.assertEqual(
            sorted(
                (row["damage_elements"], row["resistance_elements"], row["shard_state"])
                for row in products
            ),
            sorted(expected),
        )
        self.assertTrue(all(row["quantity"] == 1 for row in products))
        replay = crafting.complete(
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
        self.assertEqual(
            current["inventory_items"],
            self.reopen().character(account, character["id"])["inventory_items"],
        )

    def test_plain_later_candidate_funds_nonprecursor_recipe_without_sacrificing_rich_gear(
        self,
    ):
        from wakfu_server.element_selection import select, _required_counts

        account, generation, character, catalog, station = self.fixture()
        recipe = catalog.recipes[9854]
        self.assertEqual(recipe["raw_cvj"], 0)
        rich = self.give(account, generation, character, 29480)
        counts = _required_counts(29480)
        masks = [
            sum(1 << (i + 1) for i in range(counts[key]))
            for key in ("damage_elements", "resistance_elements")
        ]
        select(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qBB", rich["uid"], *masks),
        )
        bare = self.give(account, generation, character, 29480)
        for ingredient in recipe["ingredients"]:
            if ingredient["item_id"] != 29480:
                self.give(
                    account,
                    generation,
                    character,
                    ingredient["item_id"],
                    ingredient["quantity"],
                )
        before = next(
            row
            for row in self.store.character(account, character["id"])["inventory_items"]
            if row["uid"] == rich["uid"]
        )
        started = self.start(account, generation, character, catalog, station, 9854)
        self.finish(account, generation, character, catalog, station, started)
        current = self.store.character(account, character["id"])
        self.assertEqual(
            before,
            next(
                row for row in current["inventory_items"] if row["uid"] == rich["uid"]
            ),
        )
        self.assertFalse(
            any(row["uid"] == bare["uid"] for row in current["inventory_items"])
        )
        self.assertTrue(
            any(row["reference"] == 32331 for row in current["inventory_items"])
        )
