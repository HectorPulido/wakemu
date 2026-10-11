"""Pure invariants for durable native dungeon branch ownership."""
import copy
import json
from pathlib import Path
import unittest

from wakfu_server import dungeon_branches

ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / ".runtime/local/palacio-zollo-native-cycle-v14-20261010/native_dungeon_73.json"
)


class DungeonBranchPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topology = json.loads(CONFIG.read_text())["topology"]

    def test_v14_owns_each_physical_gate_once_and_keeps_alternatives_disjoint(self):
        branches = dungeon_branches.validate(self.topology)
        self.assertEqual({"route_34741", "route_34740"}, set(branches))
        ownership = [
            identity
            for branch in branches.values()
            for identity in branch["physical_source_ids"]
        ]
        self.assertEqual({34749, 34750, 34751, 34752}, set(ownership))
        self.assertEqual(len(ownership), len(set(ownership)))

    def test_unselected_gate_ids_and_cells_follow_only_the_durable_choice(self):
        left, right = self.topology["branch_routes"]
        unchosen = dict(self.topology, selected_branch=left["key"])
        self.assertEqual(
            set(right["physical_source_ids"]),
            set(dungeon_branches.unselected_gate_ids(unchosen)),
        )
        allowed = dungeon_branches.allowed_cells(unchosen)
        for variant in left["rooms"][:3]:
            self.assertTrue(set(map(tuple, variant["cells"])).issubset(allowed))
        for variant in right["rooms"][:3]:
            self.assertTrue(set(map(tuple, variant["cells"])).isdisjoint(allowed))
        for identity in right["physical_source_ids"]:
            gate = next(
                g for g in self.topology["physical_doors"] if g["source_id"] == identity
            )
            self.assertNotIn(tuple(gate["position"]), allowed)
        self.assertIsNone(dungeon_branches.selected_room(self.topology, 1))
        self.assertEqual(left["rooms"][0], dungeon_branches.selected_room(unchosen, 1))

    def test_duplicate_physical_gate_ownership_fails_closed(self):
        invalid = copy.deepcopy(self.topology)
        invalid["branch_routes"][1]["physical_source_ids"].append(
            invalid["branch_routes"][0]["physical_source_ids"][0]
        )
        with self.assertRaisesRegex(ValueError, "physical gate ownership"):
            dungeon_branches.validate(invalid)

    def test_unknown_physical_gate_fails_closed(self):
        invalid = copy.deepcopy(self.topology)
        invalid["branch_routes"][0]["physical_source_ids"].append(999999)
        with self.assertRaisesRegex(ValueError, "physical gate ownership"):
            dungeon_branches.validate(invalid)

    def test_unknown_selected_branch_cannot_expand_access(self):
        invalid = dict(self.topology, selected_branch="unreviewed")
        with self.assertRaisesRegex(ValueError, "Unknown durable native branch"):
            dungeon_branches.allowed_cells(invalid)
        with self.assertRaisesRegex(ValueError, "Unknown durable native branch"):
            dungeon_branches.unselected_gate_ids(invalid)
