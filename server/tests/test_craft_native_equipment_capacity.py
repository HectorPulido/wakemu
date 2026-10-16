"""Native stack capacity applies to plain crafted equipment before selection."""
import unittest
from wakfu_server.equipment import RULES
from wakfu_server.inventory_move import STACKS, ACQUISITION_STACKS
from wakfu_server.craft_planner import plan
from wakfu_server.inventory_elements import create


class CraftNativeEquipmentCapacityTests(unittest.TestCase):
    def test_bulk_equipment_uses_native_stack_not_twenty_slots(self):
        reference = next(
            ref
            for ref in sorted(RULES)
            if ref in STACKS
            and STACKS[ref]["maximum"] >= 20
            and STACKS[ref]["minimal_mergeable"]
        )
        recipe = {
            1: dict(
                recipe_id=1,
                ingredients=[dict(item_id=2021, quantity=1)],
                products=[dict(item_id=reference, quantity=1)],
            )
        }
        self.assertEqual(
            ACQUISITION_STACKS[reference]["maximum"], STACKS[reference]["maximum"]
        )
        result = plan(
            recipe,
            1,
            20,
            character_id=7,
            items=[
                dict(
                    uid=11,
                    character_id=7,
                    reference=2021,
                    quantity=40,
                    container=10,
                    slot=0,
                )
            ],
            containers=[dict(uid=10, character_id=7, kind=0, capacity=2)],
            builds=[],
        )
        self.assertEqual(len(result["product_placements"]), 1)
        self.assertEqual(result["product_placements"][0]["quantity"], 20)

    def test_existing_plain_equipment_stack_is_reused(self):
        reference = next(
            ref
            for ref in sorted(RULES)
            if ref in STACKS
            and STACKS[ref]["maximum"] >= 40
            and STACKS[ref]["minimal_mergeable"]
            and create(ref) is not None
        )
        recipe = {
            1: dict(
                recipe_id=1,
                ingredients=[dict(item_id=2021, quantity=1)],
                products=[dict(item_id=reference, quantity=1)],
            )
        }
        result = plan(
            recipe,
            1,
            20,
            character_id=7,
            items=[
                dict(
                    uid=11,
                    character_id=7,
                    reference=2021,
                    quantity=40,
                    container=10,
                    slot=0,
                ),
                dict(
                    uid=12,
                    character_id=7,
                    reference=reference,
                    quantity=5,
                    container=10,
                    slot=1,
                    **create(reference)
                ),
            ],
            containers=[dict(uid=10, character_id=7, kind=0, capacity=2)],
            builds=[],
        )
        self.assertEqual(result["product_placements"][0]["merge_uid"], 12)
        self.assertEqual(
            next(row["quantity"] for row in result["final_items"] if row["uid"] == 12),
            25,
        )
