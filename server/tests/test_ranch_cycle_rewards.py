"""Actual original criterion oracle plus explicit policy clock/roll controls."""
import copy
import json
from pathlib import Path
import random
import unittest

from wakfu_server import ranch_cycle_rewards as rewards


class RanchCycleRewardTests(unittest.TestCase):
    def test_all_original_criteria_on_native_boundary_subjects(self):
        fixture = json.loads(
            Path(__file__)
            .with_name("fixtures")
            .joinpath("ranch/native_reward_criterion_oracle.json")
            .read_text()
        )
        self.assertEqual(8, len(fixture))
        for case in fixture:
            self.assertEqual(32, len(case["outcomes"]))
            for criterion, expected in case["outcomes"].items():
                with self.subTest(
                    species=case["species"], alive=case["alive"], criterion=criterion
                ):
                    self.assertEqual(
                        expected,
                        rewards.criterion(
                            criterion,
                            species=case["species"],
                            attributes=case["attributes"],
                            alive=case["alive"],
                        ),
                    )

    def test_chronological_queue_preserves_active_time_across_arbitrary_pauses(self):
        day, start = 86400000, 864000000
        dates, queue = rewards.consume_intervals([[start, start + 10 * day]], day)
        self.assertEqual([start + n * day for n in (1, 2, 3)], dates)
        _, queue = rewards.consume_intervals(queue, day)
        _, queue = rewards.consume_intervals(queue, day)
        self.assertEqual([[start + 9 * day, start + 10 * day]], queue)
        # Three drains span packed time. Redeployment earns a new, later day
        # even though the older full cycle still awaits bounded processing.
        queue.append([start + 20 * day, start + 21 * day])
        dates, queue = rewards.consume_intervals(queue, day)
        self.assertEqual([start + 10 * day, start + 21 * day], dates)
        self.assertEqual([], queue)
        dates, queue = rewards.consume_intervals(
            [[start, start + day // 2], [start + 4 * day, start + 5 * day]], day
        )
        self.assertEqual([start + 4 * day + day // 2], dates)
        self.assertEqual([[start + 4 * day + day // 2, start + 5 * day]], queue)
        self.assertEqual(([], queue), rewards.consume_intervals(queue, day))
        self.assertEqual(
            ([], queue), rewards.consume_intervals(queue, day, max_cycles=0)
        )
        for invalid in ([[0, 10], [9, 20]], [[-1, 10]], [[10, 10]], [[True, 10]]):
            with self.assertRaises(ValueError):
                rewards.consume_intervals(invalid, day)

    def test_whole_native_species_closure_preserves_actual_attributes(self):
        species, tables = rewards.catalog()
        self.assertEqual((125, 114), (len(species), len(tables)))
        allowed = {
            row["atl"]
            for table in tables.values()
            for row in table["ugp"]
            if not row["elU"] and row["atl"]
        }
        for reference in species:
            attributes = {0: 10, 1: 5, 2: 50, 55: 2}
            before = copy.deepcopy(attributes)
            result = rewards.roll_cycle(reference, attributes, True, random.Random(42))
            self.assertEqual(
                result,
                rewards.roll_cycle(reference, attributes, True, random.Random(42)),
            )
            self.assertEqual(before, attributes)
            self.assertTrue(
                all(
                    row["reference"] in allowed and row["quantity"] > 0
                    for row in result
                )
            )

    def test_all_native_leaf_products_have_real_inventory_or_quest_routes(self):
        from wakfu_server.inventory_move import ACQUISITION_STACKS
        from wakfu_server import quest_inventory, account_quest_inventory

        _, tables = rewards.catalog()
        leaves = {
            row["atl"]
            for table in tables.values()
            for row in table["ugp"]
            if not row["elU"]
        }
        self.assertEqual(214, len(leaves))
        self.assertIn(0, leaves)
        deliverable = (
            set(ACQUISITION_STACKS)
            | quest_inventory.REFERENCES
            | account_quest_inventory.REFERENCES
        )
        self.assertEqual(set(), (leaves - {0}) - deliverable)

    def test_guaranteed_base_reward_and_unsupported_expression_rejection(self):
        result = rewards.roll_cycle(8, {}, True, random.Random(0))
        self.assertTrue(result)
        with self.assertRaises(ValueError):
            rewards.criterion("__import__('os')", species=8, attributes={}, alive=True)


if __name__ == "__main__":
    unittest.main()
