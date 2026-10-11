"""Offline planning guarantees for guild-owned chest compartments."""
from copy import deepcopy
import importlib
import struct
import sys
import unittest
from unittest.mock import patch

from wakfu_server.haven_chest import plan
from wakfu_server.characters.guild_chest import _requests, plan_move
from wakfu_server.characters.guild_chest_wire import bootstrap, contents, open_packet
from wakfu_server.items.haven_chest_wire import _blob, _scalar


class GuildChestPlannerTests(unittest.TestCase):
    def setUp(self):
        self.inventory = [
            {
                "item": {
                    "uid": 10,
                    "quantity": 9,
                    "reference": 2504,
                    "character_id": 42,
                    "container": 80,
                    "slot": 0,
                },
                "metadata": {},
            }
        ]
        self.chest = {
            "id": 1,
            "guild_id": 77,
            "name": "Guild Chest",
            "capacity": 2,
            "revision": 4,
            "items": [],
        }
        self.containers = [{"uid": 80, "character_id": 42, "kind": 0, "capacity": 2}]
        self.next_uid = 100

    def allocate(self):
        self.next_uid += 1
        return self.next_uid

    def apply(self, requests, *, deposit, character_id=42, containers=None):
        return plan(
            self.inventory,
            self.chest,
            requests,
            deposit=deposit,
            character_id=character_id,
            containers=self.containers if containers is None else containers,
            rules={2504: {"maximum": 99}},
            allocate=self.allocate,
        )

    def test_partial_transfer_preserves_quantity_and_guild_compartment_identity(self):
        inventory, chest = self.apply(
            [dict(compartment=1, uid=10, slot=0, quantity=4)], deposit=True
        )

        self.assertEqual(inventory[0]["item"]["quantity"], 5)
        self.assertEqual(chest["items"][0]["item"]["quantity"], 4)
        self.assertEqual(
            (chest["id"], chest["guild_id"], chest["revision"]), (1, 77, 4)
        )
        self.assertEqual(self.inventory[0]["item"]["quantity"], 9)

    def test_full_transfer_then_member_character_can_withdraw_shared_item(self):
        _, self.chest = self.apply(
            [dict(compartment=1, uid=10, slot=0, quantity=9)], deposit=True
        )
        self.inventory = []
        self.containers = [{"uid": 81, "character_id": 43, "kind": 0, "capacity": 2}]
        inventory, chest = plan(
            self.inventory,
            self.chest,
            [
                dict(
                    compartment=1,
                    uid=10,
                    slot=0,
                    reference=2504,
                    quantity=9,
                    container=81,
                    destination=0,
                )
            ],
            deposit=False,
            character_id=43,
            containers=self.containers,
            rules={2504: {"maximum": 99}},
            allocate=self.allocate,
        )

        self.assertEqual(inventory[0]["item"]["character_id"], 43)
        self.assertEqual(inventory[0]["item"]["container"], 81)
        self.assertEqual(chest["items"], [])

    def test_withdraw_capacity_failure_keeps_chest_item_and_input_snapshots(self):
        _, self.chest = self.apply(
            [dict(compartment=1, uid=10, slot=0, quantity=9)], deposit=True
        )
        self.inventory = [
            {
                "item": dict(
                    uid=20,
                    quantity=1,
                    reference=999,
                    character_id=42,
                    container=80,
                    slot=0,
                ),
                "metadata": {},
            },
            {
                "item": dict(
                    uid=21,
                    quantity=1,
                    reference=999,
                    character_id=42,
                    container=80,
                    slot=1,
                ),
                "metadata": {},
            },
        ]
        before = deepcopy((self.inventory, self.chest))
        with self.assertRaisesRegex(ValueError, "full"):
            self.apply(
                [
                    dict(
                        compartment=1,
                        uid=10,
                        slot=0,
                        reference=2504,
                        quantity=1,
                        container=80,
                        destination=-1,
                    )
                ],
                deposit=False,
            )
        self.assertEqual((self.inventory, self.chest), before)

    def test_partial_clone_rebinds_supported_metadata_to_new_item_uid(self):
        self.inventory[0]["metadata"] = {
            "inventory_item_elements": {
                "uid": 10,
                "damage_elements": 22,
                "resistance_elements": 0,
            }
        }
        _, chest = self.apply(
            [dict(compartment=1, uid=10, slot=0, quantity=3)], deposit=True
        )

        moved = chest["items"][0]
        self.assertEqual(
            moved["metadata"]["inventory_item_elements"]["uid"], moved["item"]["uid"]
        )
        self.assertEqual(
            self.inventory[0]["metadata"]["inventory_item_elements"]["uid"], 10
        )

    def test_foreign_compartment_and_foreign_member_inventory_are_rejected_atomically(
        self,
    ):
        before = deepcopy((self.inventory, self.chest))
        with self.assertRaisesRegex(ValueError, "Foreign chest compartment"):
            self.apply([dict(compartment=2, uid=10, slot=0, quantity=1)], deposit=True)
        with self.assertRaisesRegex(ValueError, "Foreign chest inventory"):
            self.apply(
                [dict(compartment=1, uid=10, slot=0, quantity=1)],
                deposit=True,
                character_id=43,
            )
        self.assertEqual((self.inventory, self.chest), before)

    def test_move_swaps_slots_without_changing_item_identity_or_metadata(self):
        source = {
            "id": 1,
            "guild_id": 77,
            "capacity": 2,
            "revision": 3,
            "items": [
                {
                    "slot": 0,
                    "item": {"uid": 30, "quantity": 5},
                    "metadata": {"tag": "kept"},
                },
                {"slot": 1, "item": {"uid": 31, "quantity": 2}, "metadata": {}},
            ],
        }
        destination = {
            "id": 2,
            "guild_id": 77,
            "capacity": 2,
            "revision": 7,
            "items": [{"slot": 1, "item": {"uid": 40, "quantity": 8}, "metadata": {}}],
        }
        moved_source, moved_destination = plan_move(source, 0, destination, 1)

        self.assertEqual(
            {row["item"]["uid"]: row["slot"] for row in moved_source["items"]},
            {31: 1, 40: 0},
        )
        self.assertEqual(
            {row["item"]["uid"]: row["slot"] for row in moved_destination["items"]},
            {30: 1},
        )
        self.assertEqual(moved_destination["items"][0]["metadata"], {"tag": "kept"})
        self.assertEqual(source["items"][0]["slot"], 0)

    def test_move_rejects_empty_or_identical_cells_without_mutating_inputs(self):
        chest = {
            "id": 1,
            "guild_id": 77,
            "capacity": 2,
            "items": [{"slot": 0, "item": {"uid": 1, "quantity": 1}, "metadata": {}}],
        }
        before = deepcopy(chest)
        with self.assertRaisesRegex(ValueError, "empty"):
            plan_move(chest, 1, chest, 0)
        with self.assertRaisesRegex(ValueError, "identical"):
            plan_move(chest, 0, chest, 0)
        self.assertEqual(chest, before)

    def test_cross_guild_move_and_withdrawal_uid_mismatch_are_rejected(self):
        source = {
            "id": 1,
            "guild_id": 77,
            "capacity": 2,
            "items": [{"slot": 0, "item": {"uid": 30, "quantity": 1}, "metadata": {}}],
        }
        foreign = {"id": 2, "guild_id": 78, "capacity": 2, "items": []}
        with self.assertRaisesRegex(ValueError, "Foreign guild"):
            plan_move(source, 0, foreign, 1)

        chest = dict(
            self.chest,
            items=[
                {
                    "slot": 0,
                    "item": {"uid": 30, "reference": 2504, "quantity": 1},
                    "metadata": {},
                }
            ],
        )
        request = [
            dict(
                compartment=1,
                uid=31,
                slot=0,
                reference=2504,
                quantity=1,
                container=80,
                destination=0,
            )
        ]
        with self.assertRaisesRegex(ValueError, "source changed"):
            _requests(request, chest, deposit=False)


class GuildChestWireTests(unittest.TestCase):
    def test_bootstrap_contents_and_open_match_native_carriers(self):
        chests = [
            {
                "id": 0,
                "capacity": 40,
                "enabled": True,
                "items": [
                    {"slot": 3, "item": {"uid": 10, "reference": 2504, "quantity": 2}}
                ],
            },
            {"id": 2, "capacity": 40, "enabled": False, "items": []},
        ]
        with patch(
            "wakfu_server.characters.guild_chest_wire.item_proto",
            return_value=b"\x08\x0a",
        ):
            opcode, body = bootstrap(chests, money=123)
            self.assertEqual(opcode, 14424)
            self.assertEqual(
                body,
                struct.pack(">i", 2)
                + struct.pack(">iB", 0, 1)
                + struct.pack(">iB", 2, 0)
                + struct.pack(">q", 123),
            )

            opcode, body = contents(chests)
        self.assertEqual(opcode, 14787)
        item = _blob(1, b"\x08\x0a") + _scalar(2, 3)
        compartment = _scalar(1, 0) + _scalar(2, 1) + _blob(3, item)
        disabled = _scalar(1, 2) + _scalar(2, 0)
        self.assertEqual(
            body, _blob(1, compartment) + _blob(1, disabled) + _blob(2, b"")
        )
        self.assertEqual(
            open_packet(0x24C38A),
            (12088, bytes.fromhex("010017000000000024c38a00000000")),
        )

    def test_wire_rejects_invalid_capacity_disabled_items_and_duplicate_uids(self):
        with self.assertRaisesRegex(ValueError, "capacity"):
            bootstrap([{"id": 0, "capacity": 39, "items": []}])
        with self.assertRaisesRegex(ValueError, "disabled"):
            contents(
                [
                    {
                        "id": 0,
                        "capacity": 40,
                        "enabled": False,
                        "items": [{"slot": 0, "item": {"uid": 1}}],
                    }
                ]
            )
        duplicate = [
            {"id": 0, "capacity": 40, "items": [{"slot": 0, "item": {"uid": 1}}]},
            {"id": 1, "capacity": 40, "items": [{"slot": 0, "item": {"uid": 1}}]},
        ]
        with patch(
            "wakfu_server.characters.guild_chest_wire.item_proto", return_value=b"x"
        ):
            with self.assertRaisesRegex(ValueError, "Duplicate item"):
                contents(duplicate)


class GuildChestEligibilityImportTests(unittest.TestCase):
    def test_runtime_flattened_exchange_rule_import_uses_synthetic_catalog(self):
        from wakfu_server import native_catalog
        from wakfu_server.characters.guild_chest import _eligible

        module_name = "wakfu_server.exchange_rules"
        previous = sys.modules.get(module_name)
        previous_catalog = getattr(previous, "CATALOG", None) if previous else None
        previous_items = getattr(previous, "ITEMS", None) if previous else None
        exchange_items = {
            "2504": {
                "reference": 2504,
                "binding_template": {"default_eKo": False, "enum": "NOT_BOUND"},
                "raw_criteria": {"EXCHANGE": None},
            },
            "2505": {
                "reference": 2505,
                "binding_template": {
                    "default_eKo": True,
                    "enum": "BOUND_ON_PICKUP_TO_CHARACTER",
                },
                "raw_criteria": {"EXCHANGE": None},
            },
        }
        synthetic = {
            "errors": 0,
            "raw_records": 2,
            "loaded_records": 2,
            "items": exchange_items,
        }

        with patch.object(native_catalog, "load", return_value=synthetic):
            module = (
                importlib.reload(previous)
                if previous
                else importlib.import_module(module_name)
            )

        try:
            self.assertIs(module.protocol_catalog, native_catalog)
            self.assertIsNone(
                _eligible(
                    {
                        "item": {"uid": 1, "reference": 2504},
                        "metadata": {"inventory_item_bindings": {"bound": False}},
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "Bound or nonexchangeable"):
                _eligible(
                    {
                        "item": {"uid": 2, "reference": 2504},
                        "metadata": {"inventory_item_bindings": {"bound": True}},
                    }
                )
            with self.assertRaisesRegex(ValueError, "Bound or nonexchangeable"):
                _eligible({"item": {"uid": 3, "reference": 2505}, "metadata": {}})
        finally:
            if previous is not None:
                module.CATALOG = previous_catalog
                module.ITEMS = previous_items
            else:
                sys.modules.pop(module_name, None)
                import wakfu_server

                if getattr(wakfu_server, "exchange_rules", None) is module:
                    delattr(wakfu_server, "exchange_rules")


if __name__ == "__main__":
    unittest.main()
