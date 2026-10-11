"""Budget handling for native monster spell validation previews."""
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server" / "tools"))

import validate_monster_spell_activation as validator  # noqa: E402


class MonsterValidationBudgetTests(unittest.TestCase):
    def setUp(self):
        self.modules = {
            "wakfu_server.combat_ai_capabilities": types.SimpleNamespace(
                describe_spell=lambda spell, level: {
                    "minimum": 1,
                    "maximum": 4,
                    "tags": [],
                }
            ),
            "wakfu_server.combat_npc_spell": types.SimpleNamespace(
                prepare_npc_spell=self._prepare_spell
            ),
            "wakfu_server.combat_geometry_snapshot": types.SimpleNamespace(
                source_snapshot=lambda fight: ("unchanged",)
            ),
            "monster_pending_scenarios": types.SimpleNamespace(
                enemy_search_envelope=lambda spell, level, maximum: maximum,
                scenario_recipes=lambda reference, spell: [],
                bounded_empty_targets=lambda *args, **kwargs: [],
            ),
            "monster_class_buff_scenarios": types.SimpleNamespace(
                CLASS_BUFF_RECIPES={}
            ),
            "wakfu_server.combat_native_spell_casting": types.SimpleNamespace(
                catalog=lambda: {"123": {}}
            ),
        }
        self.prepare_calls = []
        self.prepare_error = None
        self.failures_remaining = None
        self.effectful = True

    def _prepare_spell(self, fight, action, *args, **kwargs):
        self.prepare_calls.append((fight, action))
        if self.prepare_error is not None and (
            self.failures_remaining is None or self.failures_remaining > 0
        ):
            if self.failures_remaining is not None:
                self.failures_remaining -= 1
            raise self.prepare_error
        return types.SimpleNamespace(
            outcomes=[types.SimpleNamespace(applied=self.effectful)],
            events=[{"kind": "damage"}],
            packets=[b"preview"],
        )

    @staticmethod
    def fake_fight():
        return (
            types.SimpleNamespace(
                actors={7: types.SimpleNamespace(position=(1, 0))},
                walkable={(1, 0), (2, 0), (3, 0)},
            ),
            object(),
            [],
            [],
        )

    def run_case(self, cells, limit, *, scenarios=None):
        pending = self.modules["monster_pending_scenarios"]
        if scenarios is not None:
            pending.scenario_recipes = lambda reference, spell: list(scenarios)
        fixtures = []

        def build_fixture(*args, **kwargs):
            fight = self.fake_fight()
            fixtures.append((args, kwargs, fight))
            return fight

        with patch.dict(sys.modules, self.modules), patch.object(
            validator, "fixture", side_effect=build_fixture
        ):
            result = validator.run_case(100, 5, 123, 1, cells, limit)
        return result, fixtures

    def test_exhausted_budget_skips_remaining_fixtures_in_same_scenario(self):
        self.prepare_error = RuntimeError("preview failed")

        result, fixtures = self.run_case([(-8, -7), (-7, -7), (-6, -7), (-5, -7)], 1)

        self.assertEqual(len(fixtures), 1)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["status"], "pending")

    def test_later_scenario_receives_its_incremental_budget(self):
        self.prepare_error = RuntimeError("first scenario failed")
        self.failures_remaining = 1

        result, fixtures = self.run_case(
            [(-7, -7)], 1, scenarios=[{"kind": "fixture_case"}]
        )

        self.assertEqual(len(fixtures), 2)
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["status"], "validated")
        self.assertEqual(len(result["successful_targets"]), 1)

    def test_effectful_success_record_is_preserved(self):
        result, fixtures = self.run_case([(-7, -7)], 2)

        self.assertEqual(len(fixtures), 1)
        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(len(result["successful_targets"]), 1)
        success = result["successful_targets"][0]
        self.assertEqual(success["target"], [-7, -7])
        self.assertEqual(success["target_id"], 7)
        self.assertTrue(success["effectful"])
        self.assertEqual(success["outcomes"], ["namespace(applied=True)"])
        self.assertEqual(success["event_kinds"], ["damage"])
        self.assertEqual(success["packets"], 1)


if __name__ == "__main__":
    unittest.main()
