"""Native quick-transfer split stacks and atomic conservation regressions."""
import struct
import unittest
from copy import deepcopy

import test_haven_chest as fixtures

CID = fixtures.CID
from wakfu_server.haven_chest_wire import action_result, decode_deposit


def batch(rows):
    return (
        struct.pack(">hB", 1, len(CID))
        + CID.encode("ascii")
        + struct.pack(">h", len(rows))
        + b"".join(struct.pack(">qhh", *row) for row in rows)
    )


class QuickTransferTests(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.HavenChestPlannerTests()
        fixture.setUp()
        existing = fixtures.entry(uid=20, quantity=97)
        del existing["item"]["character_id"]
        del existing["item"]["container"]
        del existing["item"]["slot"]
        fixture.chest["items"] = [dict(slot=0, **existing)]
        return fixture

    def test_same_source_splits_into_existing_stack_and_empty_slot(self):
        fixture = self.fixture()
        inventory, chest = fixture.apply(
            decode_deposit(batch([(10, 0, 2), (10, 1, 7)]))
        )
        self.assertEqual(inventory, [])
        self.assertEqual([row["item"]["quantity"] for row in chest["items"]], [99, 7])
        self.assertEqual(sum(row["item"]["quantity"] for row in chest["items"]), 106)
        self.assertEqual(fixture.inventory[0]["item"]["quantity"], 9)

    def test_split_overspend_fails_without_mutating_inputs(self):
        fixture = self.fixture()
        before = deepcopy((fixture.inventory, fixture.chest))
        with self.assertRaises(ValueError):
            fixture.apply(decode_deposit(batch([(10, 0, 2), (10, 1, 8)])))
        self.assertEqual((fixture.inventory, fixture.chest), before)

    def test_duplicate_source_target_or_invalid_destinations_reject(self):
        for rows in (
            [(10, 0, 1), (10, 0, 2)],
            [(10, -1, 1), (10, -1, 2)],
            [(10, -2, 1)],
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                decode_deposit(batch(rows))

    def test_distinct_source_uids_merge_into_one_compatible_destination(self):
        fixture = self.fixture()
        fixture.inventory = [
            fixtures.entry(uid=10, quantity=2, slot=0),
            fixtures.entry(uid=11, quantity=3, slot=1),
        ]
        fixture.chest["items"][0]["item"]["quantity"] = 97
        inventory, chest = fixture.apply(
            decode_deposit(batch([(10, 0, 1), (11, 0, 1)]))
        )
        self.assertEqual(chest["items"][0]["item"]["quantity"], 99)
        self.assertEqual(chest["items"][0]["item"]["uid"], 20)
        self.assertEqual(
            sorted((row["item"]["uid"], row["item"]["quantity"]) for row in inventory),
            [(10, 1), (11, 2)],
        )

    def test_action_result_uses_original_enum_values(self):
        self.assertEqual(action_result(), (13301, b"\x00"))
        self.assertEqual(action_result(rejected=True), (13301, b"\x02"))
        with self.assertRaises(ValueError):
            action_result(rejected=1)


class ChestVariedItemsTests(unittest.TestCase):
    def test_equipment_material_seed_and_skin_round_trip_preserves_metadata(self):
        for reference, quantity in ((2044, 1), (7361, 21), (4275, 3), (11528, 25)):
            with self.subTest(reference=reference):
                fixture = fixtures.HavenChestPlannerTests()
                fixture.setUp()
                fixture.inventory = [
                    fixtures.entry(reference=reference, quantity=quantity)
                ]
                rules = {reference: {"maximum": 9999}}
                inventory, chest = fixture.apply(
                    decode_deposit(batch([(10, 0, quantity)])), rules=rules
                )
                self.assertEqual(inventory, [])
                fixture.inventory, fixture.chest = inventory, chest
                _, requests = fixtures.decode_withdraw(
                    fixtures.withdraw_body(42, reference, quantity, 80)
                )
                inventory, chest = fixture.apply(requests, deposit=False, rules=rules)
                self.assertEqual(chest["items"], [])
                self.assertEqual(inventory[0]["item"]["reference"], reference)
                self.assertEqual(inventory[0]["item"]["quantity"], quantity)

    def test_equipment_positions_reports_each_build_and_slot(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        from wakfu_server.haven_chest import _equipment_positions, _equipped

        def fields(payload):
            return {
                b"\x00": [(10, b"a")],
                b"\x01": [(10, b"b")],
                b"a": [(8, 100), (16, 3)],
                b"b": [(8, 100), (16, 7)],
            }[payload]

        character = {"builds": {0: {"equipment": "00"}, 2: {"equipment": "01"}}}
        with patch.dict(
            sys.modules, {"wakfu_server.wire": SimpleNamespace(proto_fields=fields)}
        ):
            self.assertEqual(_equipment_positions(character), {100: [(0, 3), (2, 7)]})
            self.assertEqual(_equipped(character), {100})


class DepositEquippedFilterTests(unittest.TestCase):
    def setUp(self):
        from wakfu_server.haven_chest import deposit_requests
        from wakfu_server.wire import proto_field

        self.deposit_requests = deposit_requests
        equipment = proto_field(10, proto_field(8, 10) + proto_field(16, 3))
        self.character = {
            "id": 42,
            "inventory_items": [
                dict(uid=10, character_id=42, container=80, quantity=4),
                dict(uid=11, character_id=42, container=80, quantity=5),
            ],
            "inventory_containers": [
                dict(uid=80, character_id=42, kind=0),
            ],
            "builds": {2: {"equipment": equipment.hex()}},
        }
        self.chest = dict(
            id=CID,
            capacity=10,
            compartments=[dict(id=CID, capacity=10, offset=0)],
        )

    def request(self, uid, quantity, slot=0):
        return dict(compartment=CID, uid=uid, quantity=quantity, slot=slot)

    def test_filter_skips_equipped_item_from_any_build_and_keeps_valid_rows(self):
        accepted, skipped = self.deposit_requests(
            self.character,
            self.chest,
            [self.request(10, 4), self.request(11, 5, slot=1)],
        )
        self.assertEqual(accepted, [self.request(11, 5, slot=1)])
        self.assertEqual(skipped, [10])

    def test_all_equipped_rows_become_noop_candidates(self):
        accepted, skipped = self.deposit_requests(
            self.character, self.chest, [self.request(10, 4)]
        )
        self.assertEqual(accepted, [])
        self.assertEqual(skipped, [10])

    def test_invalid_foreign_or_overspent_equipped_rows_still_reject_batch(self):
        for request, message in (
            (self.request(999, 1), "unavailable or foreign"),
            (self.request(10, 5), "exceeds owned source"),
        ):
            with self.subTest(request=request):
                with self.assertRaisesRegex(ValueError, message):
                    self.deposit_requests(self.character, self.chest, [request])
