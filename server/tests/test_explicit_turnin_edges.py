"""Ensure discovered delivery clues cannot bypass obvious criteria ambiguity."""
import importlib.util
import unittest
from pathlib import Path

PATH = (
    Path(__file__).resolve().parents[2]
    / "tools/quest-reconstruction/find_explicit_turnin_edges.py"
)
spec = importlib.util.spec_from_file_location("explicit_turnin_edges", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def document(criterion):
    return {
        "candidates": [
            {
                "id": 12,
                "title": {"es": "Misión"},
                "category_type": 3,
                "level": 1,
                "period_seconds": 0,
                "duration_seconds": 0,
                "availability": "",
                "objectives": [{"id": 34, "text": {"es": "Entregar"}}],
                "dialogue_item_evidence": [
                    {
                        "node_id": 50,
                        "choice_id": 60,
                        "node_criterion": "",
                        "choice_criterion": criterion,
                        "item_thresholds": [
                            {"item_id": 70, "quantity": 5, "operator": ">="}
                        ],
                        "node_text_es": "Hola",
                        "choice_text_es": "Entregar",
                    }
                ],
            }
        ]
    }


class ExplicitTurninCluesTest(unittest.TestCase):
    def test_exact_predicates_and_item_preserve_original_expression(self):
        criterion = "GetItemQuantity(70) >= 5 and IsAchievementRunning(12) and not IsAchievementObjectiveComplete(34)"
        rows = module.collect(document(criterion))
        self.assertEqual(
            [
                (x["quest_id"], x["objective_id"], x["item_id"], x["minimum_quantity"])
                for x in rows
            ],
            [(12, 34, 70, 5)],
        )
        self.assertEqual(rows[0]["choice_criterion"], criterion)

    def test_ambiguous_or_negated_running_are_excluded(self):
        for criterion in (
            "GetItemQuantity(70) >= 5 and IsAchievementRunning(12) and not IsAchievementObjectiveComplete(34) or True",
            "GetItemQuantity(70) >= 5 and not IsAchievementRunning(12) and not IsAchievementObjectiveComplete(34)",
            "GetItemQuantity(70) >= 5 and IsAchievementRunning(12) and not IsAchievementObjectiveComplete(999)",
        ):
            with self.subTest(criterion=criterion):
                self.assertEqual(module.collect(document(criterion)), [])


if __name__ == "__main__":
    unittest.main()
