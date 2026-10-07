import copy
import unittest

from wakfu_server import craft_catalog
from wakfu_server.items import craft_planner
from wakfu_server.wire import proto_field


CHARACTER = 50
RECIPE_ID = 2047


def item(uid, reference, quantity, container, slot, **metadata):
    return dict(
        uid=uid,
        character_id=CHARACTER,
        reference=reference,
        quantity=quantity,
        container=container,
        slot=slot,
        **metadata,
    )


def build_with_equipped(uid):
    # eHe equipment sheet: repeated field 1 entries; each entry stores its UID
    # in field 1. This is the same native shape used by inventory protection.
    return {"equipment": proto_field(10, proto_field(8, uid)).hex()}


class CraftPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = craft_catalog.load_catalog()

    def setUp(self):
        self.containers = [
            dict(uid=100, character_id=CHARACTER, kind=0, capacity=4),
            dict(uid=101, character_id=CHARACTER, kind=1, capacity=2),
        ]
        self.items = [
            item(1, 2279, 1, 100, 0),
            item(2, 2340, 3, 100, 1),
            item(3, 2340, 2, 101, 0),
        ]

    def call_plan(self, **overrides):
        args = dict(
            catalog=self.catalog,
            recipe_id=RECIPE_ID,
            batch_count=1,
            character_id=CHARACTER,
            items=self.items,
            containers=self.containers,
            builds=[],
            protected_uids=(),
        )
        args.update(overrides)
        catalog = args.pop("catalog")
        recipe_id = args.pop("recipe_id")
        batch_count = args.pop("batch_count")
        return craft_planner.plan(catalog, recipe_id, batch_count, **args)

    def test_consumes_deterministically_across_owned_bags_and_places_product(self):
        original_items = copy.deepcopy(self.items)
        plan = self.call_plan()
        self.assertEqual(
            [
                {"uid": 1, "quantity": 1},
                {"uid": 2, "quantity": 3},
                {"uid": 3, "quantity": 2},
            ],
            plan["consumed"],
        )
        self.assertEqual(
            [
                {
                    "reference": 8047,
                    "quantity": 4,
                    "container": 100,
                    "slot": 0,
                    "merge_uid": None,
                }
            ],
            plan["product_placements"],
        )
        self.assertEqual([], plan["final_items"])
        self.assertEqual(original_items, self.items)

    def test_any_saved_build_protects_the_full_equipped_stack(self):
        self.items[1]["quantity"] = 5
        with self.assertRaisesRegex(ValueError, "Insufficient unprotected"):
            self.call_plan(
                builds={"old": {"equipment": ""}, "alternate": build_with_equipped(2)}
            )

    def test_active_transfer_uid_is_protected_and_partial_metadata_is_preserved(self):
        self.items[1]["quantity"] = 5
        self.items[2]["quantity"] = 5
        self.items[1]["binding_marker"] = {"bound": True, "source": "native"}
        result = self.call_plan(protected_uids={2})
        self.assertEqual(
            [{"uid": 1, "quantity": 1}, {"uid": 3, "quantity": 5}],
            result["consumed"],
        )
        remaining = next(row for row in result["final_items"] if row["uid"] == 2)
        self.assertEqual(5, remaining["quantity"])
        self.assertEqual(
            {"bound": True, "source": "native"}, remaining["binding_marker"]
        )

    def test_products_do_not_merge_into_stacks_with_instance_metadata(self):
        self.items.extend(
            [
                item(4, 8047, 3, 100, 2, damage_elements=2, resistance_elements=0),
                item(5, 8047, 9998, 100, 3),
            ]
        )
        result = self.call_plan()
        self.assertEqual(
            [
                {
                    "reference": 8047,
                    "quantity": 1,
                    "container": 100,
                    "slot": 3,
                    "merge_uid": 5,
                },
                {
                    "reference": 8047,
                    "quantity": 3,
                    "container": 100,
                    "slot": 0,
                    "merge_uid": None,
                },
            ],
            result["product_placements"],
        )
        preserved = next(row for row in result["final_items"] if row["uid"] == 4)
        self.assertEqual(
            (2, 0), (preserved["damage_elements"], preserved["resistance_elements"])
        )

    def test_non_bag_containers_are_not_a_source_or_product_destination(self):
        self.containers.append(
            dict(uid=102, character_id=CHARACTER, kind=4, capacity=20)
        )
        self.items[2]["container"] = 102
        with self.assertRaisesRegex(ValueError, "Insufficient unprotected"):
            self.call_plan()

    def test_insufficient_materials_and_full_output_inventory_fail_without_mutation(
        self,
    ):
        self.items.pop()
        before = copy.deepcopy(self.items)
        with self.assertRaisesRegex(ValueError, "Insufficient unprotected"):
            self.call_plan()
        self.assertEqual(before, self.items)

        self.items = [item(1, 2279, 10, 100, 0), item(2, 2340, 10, 100, 1)]
        self.containers = [dict(uid=100, character_id=CHARACTER, kind=0, capacity=2)]
        before = copy.deepcopy(self.items)
        with self.assertRaisesRegex(ValueError, "inventory is full"):
            self.call_plan()
        self.assertEqual(before, self.items)

    def test_invalid_batch_foreign_rows_and_bool_quantity_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "batch quantity"):
            self.call_plan(batch_count=True)
        foreign = copy.deepcopy(self.items)
        foreign[0]["character_id"] = CHARACTER + 1
        with self.assertRaisesRegex(ValueError, "owned crafting item row"):
            self.call_plan(items=foreign)
        malformed = copy.deepcopy(self.items)
        malformed[0]["quantity"] = True
        with self.assertRaisesRegex(ValueError, "owned crafting item row"):
            self.call_plan(items=malformed)


if __name__ == "__main__":
    unittest.main()
