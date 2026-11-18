"""Regression checks for the shipped combat mission archetype batch."""

import unittest

from tools.install_mission_archetype_batches import load_batch


class MissionArchetypeBatchTests(unittest.TestCase):
    def test_shipped_batch_has_expected_complete_coverage_and_acceptance(self):
        document = load_batch()
        bindings = document["bindings"]
        by_quest = {}
        for row in bindings:
            by_quest.setdefault(row["quest_id"], []).append(row)

        self.assertEqual(len(bindings), 91)
        self.assertEqual(len(by_quest), 70)
        self.assertEqual(sum(len(rows) == 1 for rows in by_quest.values()), 63)
        self.assertEqual(sum(len(rows) > 1 for rows in by_quest.values()), 7)
        explicit = [row for row in bindings if row.get("acceptance") == "explicit"]
        self.assertEqual(len(explicit), 28)
        self.assertEqual(len({row["quest_id"] for row in explicit}), 7)
        self.assertTrue(all(row["evidence"].strip() for row in bindings))
        self.assertEqual(len({row["objective_id"] for row in bindings}), len(bindings))

    def test_batch_join_preserves_immutable_revision_and_unique_objective_joins(self):
        document = load_batch()
        self.assertEqual(document["schema"], "combat_mission_bindings_v1")
        self.assertEqual(len(document["revision"]), 64)
        self.assertEqual(
            document["bindings"],
            sorted(document["bindings"], key=lambda row: row["objective_id"]),
        )


if __name__ == "__main__":
    unittest.main()
