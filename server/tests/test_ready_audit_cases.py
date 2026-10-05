import importlib.util
from pathlib import Path
import unittest
import sys
from unittest.mock import patch


class ReadyAuditCaseTests(unittest.TestCase):
    def test_native_unlock_levels_and_basic_matrix_preserve_scope(self):
        path = Path(__file__).parents[1] / "tools/audit_ready_start.py"
        spec = importlib.util.spec_from_file_location("ready_audit_tool", path)
        module = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", [str(path.parent), *sys.path]):
            spec.loader.exec_module(module)
        spells = lambda breed, level: [
            {"id": 10, "kind": "active", "unlock_level": 1},
            {"id": 20, "kind": "passive", "unlock_level": 10},
            {"id": 30, "kind": "passive", "unlock_level": 65},
        ]
        basic = module.planned_cases([2, 1], spells, basics_only=True)
        self.assertEqual(basic, [(b, l, None) for b in (1, 2) for l in (1, 20, 200)])
        original = module.planned_cases([1], spells)
        self.assertEqual(original[3:], [(1, 20, 20), (1, 200, 20), (1, 200, 30)])
        full = module.planned_cases([1], spells, legal_passive_levels=True)
        self.assertEqual(
            full[3:],
            [(1, 10, 20), (1, 20, 20), (1, 200, 20), (1, 65, 30), (1, 200, 30)],
        )
        self.assertEqual(len(full), len(set(full)))
