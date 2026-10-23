"""Bounded original daily source contracts, without gameplay activation."""
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "daily_hunter_source_audit",
    ROOT / "server/tools/compile_daily_hunter_source_inventory.py",
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class DailyHunterSourceInventoryTests(unittest.TestCase):
    def test_all311_keep201_literal_false_separate_from110_without_producer(self):
        base = ROOT / "agents_docs/reports/parallel-readiness-20261021"
        with (base / "recurring-native-definitions.csv").open() as stream:
            definitions = list(csv.DictReader(stream))
        with (base / "recurring-source-family-classification.csv").open() as stream:
            families = list(csv.DictReader(stream))
        with gzip.open(ROOT / "server/protocol/npc-dialogues.json.gz", "rt") as stream:
            nodes = json.load(stream)["nodes"]
        result = audit.compile_inventory(definitions, families, nodes)
        self.assertEqual(result["total"], 311)
        blocked = [r for r in result["rows"] if r["literal_false_predicate"]]
        open_predicate = [r for r in result["rows"] if not r["literal_false_predicate"]]
        self.assertEqual((len(blocked), len(open_predicate)), (201, 110))
        self.assertEqual(sum(r["original_delivery"] is not None for r in blocked), 200)
        self.assertTrue(all(r["original_delivery"] is None for r in open_predicate))
        self.assertTrue(
            all(
                r["native_boss_reference"] is None
                and not r["gameplay_activation_proven"]
                and not r["automatic_acceptance"]
                and not r["obsolete_proven"]
                for r in result["rows"]
            )
        )
        self.assertTrue(
            all(
                r["original_delivery"]["literal_false"]
                for r in blocked
                if r["original_delivery"]
            )
        )
        self.assertTrue(all(len(r["native_rewards"]) == 2 for r in result["rows"]))

    def test_item_quantity_guard_cannot_rebind_objective_collision_or_drop_false(self):
        nodes = [
            dict(
                id=7,
                choices=[
                    dict(
                        id=10,
                        type=8,
                        criteria="GetItemQuantity(44) >= 10 and IsAchievementRunning(55) and False",
                    ),
                    dict(
                        id=11,
                        type=8,
                        criteria="GetItemQuantity(44) >= 10 and IsAchievementRunning(99) and not IsAchievementObjectiveComplete(55)",
                    ),
                ],
            )
        ]
        result = audit.original_deliveries(nodes)
        self.assertEqual(set(result), {55})
        self.assertEqual(
            (
                result[55]["item_reference"],
                result[55]["quantity"],
                result[55]["literal_false"],
            ),
            (44, 10, True),
        )
        with self.assertRaises(ValueError):
            audit.original_deliveries(
                nodes
                + [
                    dict(
                        id=8,
                        choices=[
                            dict(
                                id=12,
                                type=8,
                                criteria="GetItemQuantity(45) >= 10 and IsAchievementRunning(55) and False",
                            )
                        ],
                    )
                ]
            )
