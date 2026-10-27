"""Wire-sized earned bundles retain their original native roll provenance."""
from decimal import Decimal
import unittest

from wakfu_server.combat_drop_types import DropDecision
from wakfu_server.rift_loot_quantities import ReceiptIdentities, scale_ordinary


class RiftLootQuantityTests(unittest.TestCase):
    def test_large_owner_and_companion_bundles_split_without_new_rolls(self):
        def original(attempt, quantity, *, success=True, row=0):
            return DropDecision(
                -101,
                5525,
                row,
                attempt,
                27083,
                success,
                quantity if success else None,
                Decimal("0.5"),
                Decimal("0.5"),
                Decimal("0.5"),
                123,
                quantity - 1 if success else None,
                1,
                32767,
                1,
                1,
                0,
            )

        native = (
            original(0, 32767),
            original(1000, 1000),
            original(0, None, success=False, row=2),
        )
        decisions, ledger = scale_ordinary(native, 40)
        keys = {
            (row.defeated_actor_id, row.drop_row_index, row.attempt_index)
            for row in decisions
        }
        self.assertEqual(len(keys), len(decisions))
        self.assertIs(decisions[-1], native[-1])
        self.assertEqual(len(ledger), 2)
        for before, record in zip(native, ledger):
            self.assertEqual(
                sum(row["quantity"] for row in record["segments"]), before.quantity * 40
            )
            expected_band = before.attempt_index // 1000
            for segment in record["segments"]:
                self.assertTrue(1 <= segment["quantity"] <= 32767)
                self.assertEqual(segment["attempt_index"] // 1000, expected_band)
                self.assertTrue(0 <= segment["drop_row_index"] <= 32767)
            self.assertEqual(
                record["original"]["draw_numerator"], before.draw_numerator
            )
            self.assertEqual(
                record["original"]["quantity_draw_numerator"],
                before.quantity_draw_numerator,
            )
        self.assertEqual(
            sum(row.quantity for row in decisions if row.success), (32767 + 1000) * 40
        )
        self.assertTrue(all(row.draw_numerator == 123 for row in decisions))
        self.assertTrue(
            all(
                row.quantity_draw_numerator == 0
                and row.quantity_min == row.quantity_max == row.quantity
                for row in decisions
                if row.success
            )
        )
        rare_identity = ReceiptIdentities(decisions).take(-101)
        self.assertNotIn((-101, *rare_identity), keys)
        for multiplier in (0, -1, True, 100001):
            with self.subTest(multiplier=multiplier), self.assertRaises(ValueError):
                scale_ordinary(native, multiplier)
