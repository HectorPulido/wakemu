"""Regression coverage for source-only remaining dungeon geometry audit."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

TOOL = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "audit_remaining_dungeon_geometry.py"
)
spec = importlib.util.spec_from_file_location("remaining_geometry_audit", TOOL)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RemainingGeometryAuditTest(unittest.TestCase):
    def test_ordinary_excludes_accented_neo_and_special_types(self):
        for name in ("Néo-Donjon", "Neo-Donjon"):
            self.assertFalse(
                module.ordinary(
                    {"native": {"type": "DUNGEON_3_ROOMS", "name_fr": name}}
                )
            )
        self.assertFalse(
            module.ordinary({"native": {"type": "ULTIMATE_BOSS", "name_fr": "Boss"}})
        )
        self.assertTrue(
            module.ordinary(
                {"native": {"type": "DUNGEON_3_ROOMS", "name_fr": "Donjon"}}
            )
        )

    def test_missing_entry_is_not_an_empty_success(self):
        result = module.audit(
            {"key": "native:1", "name_es": "Dungeon", "native": {"name_fr": "Donjon"}},
            [],
            Path("/missing"),
        )
        self.assertEqual(result["blocker"], "no_native_entry_route")

    def test_missing_geometry_is_explicit(self):
        result = module.audit(
            {"key": "native:1", "name_es": "Dungeon", "native": {"name_fr": "Donjon"}},
            [{"route": {"key": "route", "start_map_id": 12}}],
            Path("/missing"),
        )
        self.assertEqual(
            result["routes"][0]["blocker"], "missing_native_exploration_geometry"
        )

    def test_open_geometry_without_literal_exit_remains_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "exploration-12.json").write_text(
                json.dumps({"map_id": 12, "cells": [[0, 0, 0]], "edges": []})
            )
            record = {
                "key": "native:1",
                "name_es": "Dungeon",
                "native": {"name_fr": "Donjon"},
                "native_objects": [],
                "native_exits": [],
            }
            flow = {
                "route": {"key": "route", "start_map_id": 12},
                "entry": [0, 0, 0],
                "status": "open_geometry_no_separator",
            }
            result = module.audit(record, [flow], path)
            self.assertEqual(
                result["routes"][0]["blocker"], "missing_native_exterior_exit"
            )


if __name__ == "__main__":
    unittest.main()
