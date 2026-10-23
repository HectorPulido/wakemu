"""Conversion rewards reuse capacity in equally bound ordinary resource stacks."""
import struct

from postgres_case import PostgresCase
from wakfu_server import conversion_item_actions
from wakfu_server.inventory_items import grant
from wakfu_server.combat_drop_delivery import _container_can_hold


class ConversionBoundCapacityTests(PostgresCase):
    def fixture(self, *, product_bound):
        account = self.store.register("bound-converter", "local-password")["id"]
        character = self.store.create_character(account, "Bound Converter")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        bag = character["inventory_containers"][0]
        source = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=11080,
            quantity=1,
            container=bag["uid"],
            slot=0,
            allowed_references={11080},
        )
        rule = next(
            r
            for r in conversion_item_actions.descriptors()["items"]
            if r["item_ref"] == 11080
        )
        products = {int(ref): quantity for ref, quantity in rule["products"].items()}
        product_units = {}
        for slot, reference in enumerate(products, 1):
            product_units[reference] = grant(
                self.store,
                account,
                generation,
                character["id"],
                reference=reference,
                quantity=1,
                container=bag["uid"],
                slot=slot,
                allowed_references={reference},
            )
        with self.store.connection() as db:
            for item in [source, *product_units.values()]:
                bound = True if item["uid"] == source["uid"] else product_bound
                db.execute(
                    "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,%s,%s) "
                    "ON CONFLICT(uid) DO UPDATE SET bound=EXCLUDED.bound",
                    (item["uid"], bound, item["reference"]),
                )
        for container in character["inventory_containers"]:
            if not _container_can_hold(container, character["id"]):
                continue
            first = 1 + len(products) if container["uid"] == bag["uid"] else 0
            for slot in range(first, container["capacity"]):
                with self.store.connection() as db:
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                        "VALUES(%s,9724,1,%s,%s)",
                        (character["id"], container["uid"], slot),
                    )
        return account, character, generation, source, rule, products, product_units

    def test_bound_conversion_merges_into_same_bound_product_stacks_when_bags_are_full(
        self,
    ):
        (
            account,
            character,
            generation,
            source,
            rule,
            products,
            product_units,
        ) = self.fixture(product_bound=True)
        result = conversion_item_actions.use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">iq", rule["action_id"], source["uid"]),
            in_fight=False,
        )
        by_ref = {
            i["reference"]: i
            for i in result["character"]["inventory_items"]
            if i["reference"] in products
        }
        self.assertTrue(result["binding_inherited"])
        self.assertEqual(
            {ref: item["uid"] for ref, item in product_units.items()},
            {ref: item["uid"] for ref, item in by_ref.items()},
        )
        self.assertEqual(
            {ref: quantity + 1 for ref, quantity in products.items()},
            {ref: item["quantity"] for ref, item in by_ref.items()},
        )
        with self.store.connection() as db:
            self.assertTrue(
                all(
                    r["bound"]
                    for r in db.execute(
                        "SELECT bound FROM inventory_item_bindings WHERE uid=ANY(%s)",
                        ([i["uid"] for i in by_ref.values()],),
                    )
                )
            )

    def test_bound_conversion_cannot_merge_with_unbound_stacks_or_lose_source(self):
        (
            account,
            character,
            generation,
            source,
            rule,
            products,
            product_units,
        ) = self.fixture(product_bound=False)
        before = self.store.character(account, character["id"])["inventory_items"]
        from wakfu_server.achievements.rewards import RewardCapacity

        with self.assertRaises(RewardCapacity):
            conversion_item_actions.use(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">iq", rule["action_id"], source["uid"]),
                in_fight=False,
            )
        self.assertEqual(
            before, self.store.character(account, character["id"])["inventory_items"]
        )
