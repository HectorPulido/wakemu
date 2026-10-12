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

    def test_duplicate_or_invalid_destinations_reject(self):
        for rows in (
            [(10, 0, 1), (10, 0, 2)],
            [(10, 0, 1), (11, 0, 2)],
            [(10, -1, 1), (10, -1, 2)],
            [(10, -2, 1)],
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                decode_deposit(batch(rows))

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
