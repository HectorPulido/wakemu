import unittest
from unittest.mock import Mock

from wakfu_server.combat_arena_policy import cell_budget, size_range
from wakfu_server.combat_arena_selection import compact_encounter
from test_combat_adaptive_arena import grid


class CombatArenaPolicyTests(unittest.TestCase):
    def test_database_changes_apply_to_next_read(self):
        db = Mock()
        db.execute.return_value.fetchone.side_effect = [
            {"value": 1500},
            {"value": 900},
            {"value": 2500},
        ]
        self.assertEqual([cell_budget(db) for _ in range(3)], [1500, 900, 2500])

    def test_invalid_or_missing_database_policy_is_rejected(self):
        db = Mock()
        for value in (None, True, 899, 2501, 1500.5, "1500"):
            db.execute.return_value.fetchone.return_value = {"value": value}
            with self.assertRaises(ValueError):
                cell_budget(db)
        db.execute.return_value.fetchone.return_value = None
        with self.assertRaises(ValueError):
            cell_budget(db)

    def test_arena_size_range_is_read_and_validated_on_each_read(self):
        db = Mock()
        db.execute.return_value.fetchone.side_effect = [
            {"value": {"minimum": 7, "maximum": 20}},
            {"value": {"minimum": 8, "maximum": 12}},
        ]
        self.assertEqual(size_range(db), (7, 20))
        self.assertEqual(size_range(db), (8, 12))
        for invalid in (
            None,
            20,
            {"minimum": 6, "maximum": 20},
            {"minimum": 15, "maximum": 14},
            {"minimum": 7, "maximum": 51},
            {"minimum": True, "maximum": 20},
            {"minimum": 7, "maximum": 20, "extra": 1},
        ):
            db.execute.return_value.fetchone.side_effect = None
            db.execute.return_value.fetchone.return_value = {"value": invalid}
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                size_range(db)
        db.execute.return_value.fetchone.side_effect = None
        db.execute.return_value.fetchone.return_value = None
        with self.assertRaises(ValueError):
            size_range(db)

    def test_configured_budget_preserves_automatic_rectangle_selection(self):
        terrain = grid(45, 45)
        selected = compact_encounter(
            terrain, (20, 20, 0), [(22, 20, 0)], automatic_cell_budget=1500
        )
        cells = selected["cells"]
        width = max(c[0] for c in cells) - min(c[0] for c in cells) + 1
        height = max(c[1] for c in cells) - min(c[1] for c in cells) + 1
        self.assertEqual(len(cells), width * height)
        self.assertLess(len(cells), 1500)
        self.assertGreaterEqual(len(cells), 36)

    def test_configured_budget_caps_rectangle_and_keeps_duel_minimum(self):
        selected = compact_encounter(
            grid(45, 45),
            (20, 20, 0),
            [(22, 20, 0)],
            minimum_cells=900,
            minimum_dimensions=(30, 30),
            automatic_cell_budget=900,
        )
        self.assertEqual(len(selected["cells"]), 900)

    def test_explicit_budget_retains_original_selection(self):
        selected = compact_encounter(
            grid(20, 20),
            (10, 10, 0),
            [(12, 10, 0)],
            100,
            automatic_cell_budget=1500,
        )
        self.assertLessEqual(len(selected["cells"]), 100)

    def test_gameplay_callers_pass_postgresql_automatic_budget(self):
        import ast
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        for filename in (
            "local_game_server.py",
            "wakfu_server/combat/friendly_duel_runtime.py",
        ):
            tree = ast.parse((root / filename).read_text())
            calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "local_arena"
            ]
            self.assertEqual(len(calls), 1, filename)
            self.assertIn(
                "automatic_cell_budget", {item.arg for item in calls[0].keywords}
            )
            readers = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "cell_budget"
            ]
            self.assertEqual(len(readers), 1, filename)
