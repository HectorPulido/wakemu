"""Regressions for evidence-only boss readiness checks."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "boss_audit",
    Path(__file__).parents[1] / "tools" / "audit_dungeon_boss_abilities.py",
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class BossAbilityAuditTests(unittest.TestCase):
    def monster(self, parameter=-1):
        return dict(
            ref=1,
            name="Boss",
            min_level=2,
            native_abilities=[dict(spell_id=10, level_parameter=parameter)],
        )

    def test_actor_level_owned_spell_checks_exact_native_level(self):
        casting = {"10": {"levels": [[0, 0, [8]], [0, 0, [9]]]}}
        result = audit.inspect_boss(self.monster(), casting, {"9": {}})
        self.assertEqual(result["owned_root_coverage"], "all_present")
        self.assertEqual(result["spells"][0]["roots"], [9])
        self.assertEqual(result["special_mechanic_validation"], "not_proved")

    def test_missing_mandatory_root_is_unsupported(self):
        casting = {"10": {"levels": [[0, 0, [8]], [0, 0, [9, 11]]]}}
        result = audit.inspect_boss(self.monster(), casting, {"9": {}})
        self.assertEqual(result["owned_root_coverage"], "incomplete")
        self.assertIn(
            "owned_spell_root_not_in_compiled_npc_catalog",
            result["spells"][0]["reasons"],
        )

    def test_missing_casting_level_does_not_select_last_level(self):
        result = audit.inspect_boss(
            self.monster(), {"10": {"levels": [[0, 0, [9]]]}}, {"9": {}}
        )
        self.assertEqual(result["owned_root_coverage"], "incomplete")
        self.assertEqual(result["spells"][0]["roots"], [])

    def test_no_owned_spells_is_not_complete_boss_validation(self):
        monster = self.monster()
        monster["native_abilities"] = []
        self.assertEqual(
            audit.inspect_boss(monster, {}, {})["owned_root_coverage"], "incomplete"
        )
