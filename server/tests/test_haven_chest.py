"""Chest conservation, atomic planning, ownership and captured native framing."""
from copy import deepcopy
import struct
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from wakfu_server.haven_chest import _json, _unjson, plan, validate_open
from wakfu_server.haven_chest_wire import decode_deposit, decode_withdraw, open_packet


CID = "7715766b-96c6-418e-9495-c1fccc043332"


def deposit_body(uid, quantity, slot=0, compartment=CID):
    identity = compartment.encode("ascii")
    return (
        struct.pack(">hB", 1, len(identity))
        + identity
        + struct.pack(">hqhh", 1, uid, slot, quantity)
    )


def withdraw_body(
    actor, reference, quantity, container, slot=0, destination=-1, compartment=CID
):
    identity = compartment.encode("ascii")
    return (
        struct.pack(">qB", actor, len(identity))
        + identity
        + struct.pack(">hihhqh", 1, reference, slot, quantity, container, destination)
    )


def entry(
    uid=10,
    quantity=9,
    *,
    slot=0,
    reference=2504,
    character_id=42,
    container=80,
    metadata=None
):
    return dict(
        item=dict(
            uid=uid,
            quantity=quantity,
            slot=slot,
            reference=reference,
            character_id=character_id,
            container=container,
        ),
        metadata=metadata or {},
    )


class HavenChestPlannerTests(unittest.TestCase):
    def setUp(self):
        self.inventory = [entry()]
        self.chest = dict(id=CID, account_id=7, capacity=2, revision=0, items=[])
        self.containers = [dict(uid=80, character_id=42, kind=0, capacity=2)]
        self.next_uid = 100

    def allocate(self):
        self.next_uid += 1
        return self.next_uid

    def apply(self, requests, deposit=True, **changes):
        args = dict(
            character_id=42,
            containers=self.containers,
            rules={2504: {"maximum": 99}},
            allocate=self.allocate,
        )
        args.update(changes)
        return plan(self.inventory, self.chest, requests, deposit=deposit, **args)

    def test_partial_deposit_conserves_quantity_and_source_identity(self):
        inv, chest = self.apply(decode_deposit(deposit_body(10, 4)))
        self.assertEqual((inv[0]["item"]["uid"], inv[0]["item"]["quantity"]), (10, 5))
        self.assertEqual(chest["items"][0]["item"]["quantity"], 4)
        self.assertNotEqual(chest["items"][0]["item"]["uid"], 10)
        self.assertEqual(self.inventory[0]["item"]["quantity"], 9)
        self.assertNotIn("character_id", chest["items"][0]["item"])

    def test_whole_deposit_keeps_uid_then_whole_withdraw_restores_it(self):
        inv, chest = self.apply(decode_deposit(deposit_body(10, 9)))
        self.assertEqual(inv, [])
        self.assertEqual(chest["items"][0]["item"]["uid"], 10)
        self.inventory, self.chest = inv, chest
        _, request = decode_withdraw(withdraw_body(42, 2504, 9, 80))
        inv, chest = self.apply(request, deposit=False)
        self.assertEqual(chest["items"], [])
        self.assertEqual(inv[0]["item"], entry()["item"])

    def test_rich_metadata_survives_deposit_withdraw_exactly(self):
        metadata = {
            "inventory_item_shards": {
                "uid": 10,
                "shard_state": b"\x18\x01\xf0\x03\x02",
            },
            "inventory_item_elements": {
                "uid": 10,
                "damage_elements": 22,
                "resistance_elements": 0,
            },
            "inventory_item_bindings": {
                "uid": 10,
                "bound": True,
                "template_reference": 2504,
            },
        }
        self.inventory[0]["metadata"] = metadata
        self.inventory[0]["item"]["shard_state"] = metadata["inventory_item_shards"][
            "shard_state"
        ]
        before = deepcopy(self.inventory[0])
        self.inventory, self.chest = self.apply(decode_deposit(deposit_body(10, 9)))
        _, request = decode_withdraw(withdraw_body(42, 2504, 9, 80))
        inv, _ = self.apply(request, deposit=False)
        self.assertEqual(inv[0], before)
        self.assertEqual(_unjson(_json(inv)), inv)

    def test_partial_metadata_clone_uses_allocated_uid(self):
        self.inventory[0]["metadata"] = {
            "inventory_item_elements": {
                "uid": 10,
                "damage_elements": 22,
                "resistance_elements": 0,
            }
        }
        inv, chest = self.apply(decode_deposit(deposit_body(10, 3)))
        moved = chest["items"][0]
        self.assertEqual(
            moved["metadata"]["inventory_item_elements"]["uid"], moved["item"]["uid"]
        )
        self.assertEqual(inv[0]["metadata"]["inventory_item_elements"]["uid"], 10)

    def test_second_character_can_withdraw_account_owned_item(self):
        self.inventory, self.chest = self.apply(decode_deposit(deposit_body(10, 9)))
        self.containers = [dict(uid=81, character_id=43, kind=0, capacity=2)]
        _, request = decode_withdraw(withdraw_body(43, 2504, 9, 81))
        inv, chest = self.apply(request, deposit=False, character_id=43)
        self.assertEqual(inv[0]["item"]["character_id"], 43)
        self.assertEqual(inv[0]["item"]["container"], 81)
        self.assertEqual(chest["items"], [])

    def test_full_chest_rejects_without_changing_inputs(self):
        self.chest["capacity"] = 1
        self.chest["items"] = [
            dict(slot=0, item=dict(uid=20, reference=999, quantity=1), metadata={})
        ]
        before = deepcopy((self.inventory, self.chest))
        with self.assertRaisesRegex(ValueError, "full"):
            self.apply(decode_deposit(deposit_body(10, 3, slot=-1)))
        self.assertEqual((self.inventory, self.chest), before)

    def test_full_inventory_rejects_without_losing_chest_item(self):
        self.inventory, self.chest = self.apply(decode_deposit(deposit_body(10, 4)))
        self.inventory = [
            entry(uid=11, slot=0, reference=999),
            entry(uid=12, slot=1, reference=999),
        ]
        before = deepcopy((self.inventory, self.chest))
        _, requests = decode_withdraw(withdraw_body(42, 2504, 2, 80))
        with self.assertRaisesRegex(ValueError, "full"):
            self.apply(requests, deposit=False)
        self.assertEqual((self.inventory, self.chest), before)

    def test_automatic_destination_merges_compatible_stack_even_when_full(self):
        self.chest["capacity"] = 1
        self.chest["items"] = [
            dict(slot=0, item=dict(uid=20, reference=2504, quantity=3), metadata={})
        ]
        inv, chest = self.apply(decode_deposit(deposit_body(10, 4, slot=-1)))
        self.assertEqual(chest["items"][0]["item"]["quantity"], 7)
        self.assertEqual(inv[0]["item"]["quantity"], 5)
        self.assertEqual(self.next_uid, 100)

    def test_different_metadata_cannot_merge(self):
        self.chest["items"] = [
            dict(
                slot=0,
                item=dict(uid=20, reference=2504, quantity=3),
                metadata={
                    "inventory_item_recycling_state": {"uid": 20, "unidentified": True}
                },
            )
        ]
        with self.assertRaisesRegex(ValueError, "incompatible"):
            self.apply(decode_deposit(deposit_body(10, 4)))

    def test_batch_failure_rolls_back_earlier_planned_item(self):
        requests = decode_deposit(deposit_body(10, 4)) + [
            dict(compartment=CID, uid=999, slot=1, quantity=1)
        ]
        before = deepcopy((self.inventory, self.chest))
        with self.assertRaises(ValueError):
            self.apply(requests)
        self.assertEqual((self.inventory, self.chest), before)

    def test_foreign_compartment_item_and_container_are_rejected(self):
        for request in [
            dict(compartment="other", uid=10, slot=0, quantity=1),
            dict(compartment=CID, uid=999, slot=0, quantity=1),
        ]:
            with self.assertRaises(ValueError):
                self.apply([request])
        self.inventory, self.chest = self.apply(decode_deposit(deposit_body(10, 9)))
        _, request = decode_withdraw(withdraw_body(42, 2504, 1, 999))
        with self.assertRaises(ValueError):
            self.apply(request, deposit=False)

    def test_oversized_quantity_and_slot_and_unknown_rules_reject(self):
        for body in (deposit_body(10, 10), deposit_body(10, 1, slot=9)):
            with self.assertRaises(ValueError):
                self.apply(decode_deposit(body))
        with self.assertRaises(ValueError):
            self.apply(decode_deposit(deposit_body(10, 1)), rules={})


class HavenChestWireTests(unittest.TestCase):
    def test_captured_deposit_and_withdraw_are_decoded(self):
        deposit = bytes.fromhex(
            "00012437373135373636622d393663362d343138652d393439352d6331666363633034333333320001006573c0f800038400360001"
        )
        (request,) = decode_deposit(deposit)
        self.assertEqual(
            request, dict(compartment=CID, uid=0x6573C0F8000384, slot=54, quantity=1)
        )
        withdraw = bytes.fromhex(
            "000000000024c38a2437373135373636622d393663362d343138652d393439352d633166636363303433333332000100004f320036000100676f39660000e80000"
        )
        actor, requests = decode_withdraw(withdraw)
        self.assertEqual(actor, 0x24C38A)
        self.assertEqual(
            requests[0],
            dict(
                compartment=CID,
                reference=20274,
                slot=54,
                quantity=1,
                container=0x676F39660000E8,
                destination=0,
            ),
        )

    def test_bootstrap_uses_owned_compartment_and_complete_slot_snapshot(self):
        from wakfu_server.haven_chest_wire import bootstrap, _blob, _scalar

        chest = dict(
            id=CID,
            account_id=7,
            capacity=100,
            items=[dict(slot=54, item=entry()["item"])],
        )
        item_proto = b"\x08\x0a\x10\xc8\x13\x18\x09"
        with patch("wakfu_server.inventory_items.item_proto", return_value=item_proto):
            opcode, body = bootstrap(chest)
        expected_items = _blob(1, _blob(1, item_proto) + _scalar(2, 54) + _scalar(3, 0))
        expected_compartment = (
            _blob(1, CID.encode())
            + _scalar(2, 7)
            + _blob(3, b"Haven chest")
            + _scalar(5, 0)
            + _scalar(7, 100)
            + _scalar(8, 0)
            + _blob(9, expected_items)
        )
        self.assertEqual(opcode, 318)
        self.assertEqual(
            body,
            struct.pack(">hI", 1, len(expected_compartment))
            + expected_compartment
            + b"\x01",
        )
        chest["items"][0]["slot"] = 100
        with self.assertRaises(ValueError):
            bootstrap(chest)

    def test_captured_open_packet_matches_native_body(self):
        self.assertEqual(
            open_packet(0x24C38A),
            (12088, bytes.fromhex("01001f000000000024c38a00000000")),
        )

    def test_malformed_lengths_counts_and_duplicates_reject(self):
        body = deposit_body(10, 1)
        for malformed in (
            b"",
            body[:-1],
            body + b"\x00",
            b"\x00\x00",
            deposit_body(0, 1),
            deposit_body(10, 0),
        ):
            with self.assertRaises(ValueError):
                decode_deposit(malformed)
        prefix = struct.pack(">hB", 1, len(CID)) + CID.encode() + struct.pack(">h", 2)
        with self.assertRaises(ValueError):
            decode_deposit(prefix + struct.pack(">qhh", 10, 0, 1) * 2)
        body = withdraw_body(42, 2504, 1, 80)
        for malformed in (body[:-1], body + b"\x00", withdraw_body(0, 2504, 1, 80)):
            with self.assertRaises(ValueError):
                decode_withdraw(malformed)

    def test_open_checks_owner_native_identity_action_proximity_and_fight(self):
        character = dict(id=42, map_id=9, instance_id=42, x=0, y=-3, z=0)
        bag = SimpleNamespace(
            is_owner=True, owns=lambda char: char["instance_id"] == 42
        )
        obj = dict(id=13261, map_id=9, type="AccountChest", x=0, y=-4, z=0)
        body = struct.pack(">qHH", 13261, 12, 0)
        self.assertEqual(
            validate_open(character, bag, body, [obj], fight_active=False), 13261
        )
        for c, b, packet, objects, fighting in (
            (character, bag, body, [obj], True),
            (character, None, body, [obj], False),
            (character, SimpleNamespace(is_owner=False), body, [obj], False),
            (dict(character, x=99), bag, body, [obj], False),
            (character, bag, struct.pack(">qHH", 13261, 12, 1), [obj], False),
            (character, bag, body, [dict(obj, type="LootChest")], False),
        ):
            with self.assertRaises(ValueError):
                validate_open(c, b, packet, objects, fight_active=fighting)


if __name__ == "__main__":
    unittest.main()
