"""Exercise the audit's actual nested placement helper without loading catalogs."""
import ast
import copy
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from wakfu_server.combat_arena_selection import bounded_arena


class SramTrapOwnerPlacementTests(unittest.TestCase):
    def placement(self, geometry):
        source = Path(__file__).resolve().parents[1] / "tools/audit_sram_trap_manual.py"
        tree = ast.parse(source.read_text())
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "separated_owner_geometry"
        )
        namespace = {"details": {}}
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        module = types.ModuleType("audit_ready_start")
        module.bounded_arena = bounded_arena
        with patch.dict(sys.modules, {"audit_ready_start": module}):
            result = namespace[function.name](
                geometry, (0, 0, 0), (1, 0, 0), 11, 200, None
            )
        return result, namespace["details"]

    @staticmethod
    def topology(path):
        edges = [(a, b) for a, b in zip(path, path[1:])]
        return {
            "map_id": 777,
            "cells": path,
            "edges": edges + [(b, a) for a, b in edges],
        }

    def test_owner_placement_uses_a_free_separated_same_floor_native_cell(self):
        geometry = self.topology([(x, 0, 0) for x in range(9)])
        original = copy.deepcopy(geometry)
        (owner, enemy, terrain), details = self.placement(geometry)
        self.assertEqual(owner, (0, 0, 0))
        self.assertIn(enemy, terrain["cells"])
        self.assertNotEqual(enemy, owner)
        self.assertEqual(enemy[2], owner[2])
        self.assertGreaterEqual(
            max(abs(enemy[0] - owner[0]), abs(enemy[1] - owner[1])), 6
        )
        self.assertEqual(geometry, original)
        self.assertLessEqual(set(terrain["edges"]), set(geometry["edges"]))
        self.assertEqual(details["preplacement"]["enemy"], enemy)

    def test_insufficient_native_same_floor_spacing_rejects(self):
        geometry = self.topology(
            [(0, 0, 0), (1, 0, 0)] + [(x, 0, 1) for x in range(2, 9)]
        )
        with self.assertRaisesRegex(ValueError, "separated native NPC placement"):
            self.placement(geometry)
