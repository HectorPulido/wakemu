"""Trap dependencies must enter the same area closure as configured eYQ areas."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_class_dependency_inventory import build


class TrapDependencyInventoryTests(unittest.TestCase):
    def test_trap_area_children_and_states_are_included_without_execution_claim(self):
        graph = dict(
            effects={"1": [308, [], [778]], "2": [304, [], [99]], "3": [400, [], []]},
            spells={"5182": [1]},
            areas={"778": [2]},
            states={"99": [3]},
            criteria={},
        )
        ledger = dict(
            spells=[
                dict(
                    spell_id=5182,
                    name="Trap",
                    kind="active",
                    origin="grant",
                    breeds=[4],
                )
            ]
        )
        row = build(graph, ledger, dict(breeds=[]), {308, 304, 400})[0]
        self.assertEqual(row["dependencies"]["area"], [778])
        self.assertEqual(row["dependencies"]["state"], [99])
        self.assertEqual(row["dependencies"]["effect"], [1, 2, 3])
        self.assertEqual(row["complete_semantic_verification"], "unknown")

    def test_missing_trap_definition_is_reported_instead_of_silent_complete_closure(
        self,
    ):
        graph = dict(
            effects={"1": [308, [], [2135]]},
            spells={"8507": [1]},
            areas={},
            states={},
            criteria={},
        )
        ledger = dict(
            spells=[
                dict(
                    spell_id=8507,
                    name="TrapII",
                    kind="active",
                    origin="grant",
                    breeds=[4],
                )
            ]
        )
        row = build(graph, ledger, dict(breeds=[]), {308})[0]
        self.assertEqual(row["unresolved_structural_references"]["area"], [2135])
