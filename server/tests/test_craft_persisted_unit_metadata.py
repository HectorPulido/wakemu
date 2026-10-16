"""Craft products do not inherit resident unit overrides invisible to hydration."""
from postgres_case import PostgresCase
from wakfu_server.equipment import RULES
from wakfu_server.inventory_move import STACKS
from wakfu_server.inventory_elements import create
from wakfu_server.inventory_items import grant
from wakfu_server.exchange_rules import ITEMS
from wakfu_server.crafting import _plan


class CraftPersistedUnitMetadataTests(PostgresCase):
    def scenario(self):
        account = self.store.register("craft-metadata", "local-password")["id"]
        character = self.store.create_character(account, "Craft Metadata")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        bag = character["inventory_containers"][0]["uid"]
        reference = next(
            ref
            for ref in sorted(RULES)
            if ref in STACKS
            and STACKS[ref]["maximum"] >= 40
            and STACKS[ref]["minimal_mergeable"]
            and create(ref) is not None
            and ITEMS[str(ref)]["binding_template"]["default_eKo"] is False
        )
        for ref, quantity, slot in ((2021, 40, 0), (reference, 5, 1)):
            item = grant(
                self.store,
                account,
                generation,
                character["id"],
                reference=ref,
                quantity=quantity,
                container=bag,
                slot=slot,
                allowed_references={ref},
            )
        recipe = dict(
            recipe_id=1,
            ingredients=[dict(item_id=2021, quantity=1)],
            products=[dict(item_id=reference, quantity=1)],
        )
        return account, character, item, recipe

    def assert_marked_stack_stays_distinct(self, kind):
        account, character, resident, recipe = self.scenario()
        with self.store.connection() as db:
            _, plain = _plan(
                self.store, db, account, character["id"], {1: recipe}, recipe, 20
            )
            self.assertEqual(
                plain["product_placements"][0]["merge_uid"], resident["uid"]
            )
            if kind == "binding":
                db.execute(
                    "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,true,%s)",
                    (resident["uid"], resident["reference"]),
                )
            else:
                db.execute(
                    "INSERT INTO inventory_item_recycling_state(uid,socketed) VALUES(%s,true)",
                    (resident["uid"],),
                )
            _, marked = _plan(
                self.store, db, account, character["id"], {1: recipe}, recipe, 20
            )
        self.assertEqual(marked["product_placements"][0]["merge_uid"], None)
        self.assertEqual(
            next(
                row["quantity"]
                for row in marked["final_items"]
                if row["uid"] == resident["uid"]
            ),
            5,
        )
        self.assertEqual(sum(row["quantity"] for row in marked["consumed"]), 20)

    def test_instance_bound_resident_does_not_absorb_new_crafts(self):
        self.assert_marked_stack_stays_distinct("binding")

    def test_socket_marked_resident_does_not_absorb_new_crafts(self):
        self.assert_marked_stack_stays_distinct("recycling")
