"""Candidate extraction never confuses duplicate names with proven edges."""
import importlib.util
from pathlib import Path
import unittest


PATH = (
    Path(__file__).resolve().parents[2]
    / "tools/quest-reconstruction/find_child_quest_links.py"
)
SPEC = importlib.util.spec_from_file_location("quest_child_link_candidates", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def quest(identity, *objectives):
    return {
        "d": identity,
        "native_class": "aJM",
        "aqb": False,
        "cjJ": [
            {"d": objective, "ckc": "", "cke": "", "ckf": []}
            for objective in objectives
        ],
    }


class ChildQuestCandidateTests(unittest.TestCase):
    def test_exact_multilingual_relationship_and_prerequisite(self):
        parent = quest(1, 10)
        parent["cjJ"][0]["ckc"] = "IsAchievementObjectiveComplete(9)"
        data = {
            "definitions": [parent, quest(2)],
            "translations": {
                "en": {
                    "content.62.2": "First Lesson",
                    "content.64.10": 'Complete the quest "First Lesson"',
                },
                "es": {
                    "content.62.2": "Primera lección",
                    "content.64.10": "Completar la misión Primera lección",
                },
            },
        }
        (row,) = MODULE.extract(data)
        self.assertEqual(
            (row["parent_id"], row["objective_id"], row["possible_child_ids"]),
            (1, 10, [2]),
        )
        self.assertEqual(row["status"], "unique_exact_multilingual")
        self.assertEqual(
            row["objective_prerequisite"], "IsAchievementObjectiveComplete(9)"
        )

    def test_duplicate_titles_and_conflicts_remain_unresolved(self):
        data = {
            "definitions": [quest(1, 10), quest(2), quest(3)],
            "translations": {
                "en": {
                    "content.62.2": "Same",
                    "content.62.3": "Same",
                    "content.64.10": "Complete the quest: Same",
                },
            },
        }
        (row,) = MODULE.extract(data)
        self.assertEqual(row["status"], "ambiguous")
        self.assertEqual(row["possible_child_ids"], [2, 3])
        data["translations"]["es"] = {
            "content.62.2": "Otro",
            "content.62.3": "Mismo",
            "content.64.10": "Completar la misión Mismo",
        }
        (row,) = MODULE.extract(data)
        self.assertEqual(row["status"], "resolved_by_cross_language")
        self.assertEqual(row["possible_child_ids"], [3])
        data["translations"]["en"]["content.62.3"] = "Different"
        (row,) = MODULE.extract(data)
        self.assertEqual(row["status"], "conflicting_languages")
        self.assertEqual(row["possible_child_ids"], [])

    def test_no_self_edges_or_unrelated_text(self):
        data = {
            "definitions": [quest(1, 10), quest(2)],
            "translations": {
                "en": {
                    "content.62.1": "First",
                    "content.62.2": "Second",
                    "content.64.10": 'Complete the quest "First"',
                },
            },
        }
        self.assertEqual(MODULE.extract(data), [])
        data["translations"]["en"]["content.64.10"] = "Talk about the quest Second"
        self.assertEqual(MODULE.extract(data), [])


if __name__ == "__main__":
    unittest.main()
