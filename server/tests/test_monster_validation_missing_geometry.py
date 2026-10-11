"""Missing native spell geometry should leave a validation case pending."""
from pathlib import Path
import sys
import unittest
import importlib
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server" / "tools"))
sys.path.insert(0, str(ROOT / "server" / "tests"))

import validate_monster_spell_activation as validator  # noqa: E402

budget_tests = importlib.import_module("test_monster_validation_budget")


class MonsterValidationMissingGeometryTests(unittest.TestCase):
    def setUp(self):
        self.harness = budget_tests.MonsterValidationBudgetTests()
        self.harness.setUp()
        self.pending = self.harness.modules["monster_pending_scenarios"]

    def test_missing_native_casting_root_returns_pending_without_fixture_or_attempt(
        self,
    ):
        self.pending.enemy_search_envelope = lambda *args: (_ for _ in ()).throw(
            ValueError("Missing original summon level mode")
        )
        with patch.dict(sys.modules, self.harness.modules), patch.object(
            validator, "fixture"
        ) as fixture:
            result = validator.run_case(100, 5, 123, 1, [(-7, -7)], 3)

        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["attempts"], 0)
        self.assertEqual(
            result["errors"],
            {"scene_search: ValueError: Missing original summon level mode": 1},
        )
        fixture.assert_not_called()

    def test_runtime_error_from_geometry_lookup_is_not_hidden(self):
        self.pending.enemy_search_envelope = lambda *args: (_ for _ in ()).throw(
            RuntimeError("geometry catalog is corrupt")
        )
        with patch.dict(sys.modules, self.harness.modules), patch.object(
            validator, "fixture"
        ) as fixture:
            with self.assertRaisesRegex(RuntimeError, "geometry catalog is corrupt"):
                validator.run_case(100, 5, 123, 1, [(-7, -7)], 3)

        fixture.assert_not_called()

    def test_ordinary_spell_skips_discarded_empty_cell_search(self):
        calls = []
        self.pending.bounded_empty_targets = lambda *args, **kwargs: calls.append(args)
        self.harness.modules[
            "wakfu_server.combat_native_spell_casting"
        ].catalog = lambda: {"123": {"free_cell": False}}
        with patch.dict(sys.modules, self.harness.modules), patch.object(
            validator,
            "fixture",
            side_effect=lambda *args, **kwargs: self.harness.fake_fight(),
        ):
            result = validator.run_case(100, 5, 123, 1, [(-7, -7)], 2)

        self.assertEqual(result["status"], "validated")
        self.assertEqual(calls, [])
        self.assertEqual(result["successful_targets"][0]["target"], [-7, -7])

    def test_free_cell_spell_searches_and_prioritizes_empty_targets(self):
        empty_target = (-6, -7)
        calls = []

        def bounded_targets(*args, **kwargs):
            calls.append((args, kwargs))
            return [empty_target]

        self.pending.bounded_empty_targets = bounded_targets
        self.harness.modules[
            "wakfu_server.combat_native_spell_casting"
        ].catalog = lambda: {"123": {"free_cell": True}}
        with patch.dict(sys.modules, self.harness.modules), patch.object(
            validator,
            "fixture",
            side_effect=lambda *args, **kwargs: self.harness.fake_fight(),
        ):
            result = validator.run_case(100, 5, 123, 1, [(-7, -7)], 2)

        self.assertEqual(result["status"], "validated")
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["successful_targets"][0]["target"], list(empty_target))
        self.assertIsNone(result["successful_targets"][0]["target_id"])


if __name__ == "__main__":
    unittest.main()
