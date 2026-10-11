"""Bounded missing spell discovery follows native typed edges only."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from export_monster_summon_dependencies import compact
from plan_monster_spell_supplement import missing_spell_plan


class MissingSpellSupplementTests(unittest.TestCase):
    def sources(self):
        effects = {
            "1": dict(effect_class=315, children=[], parameters_by_level=[[1951]]),
            "2": dict(effect_class=304, children=[], parameters_by_level=[[8721]]),
            "3": dict(
                effect_class=649, children=[4], parameters_by_level=[[3, -1, 8331, 1]]
            ),
            "4": dict(effect_class=330, children=[3], parameters_by_level=[]),
        }
        tables = compact(
            dict(
                effects=effects,
                spells={},
                states={"8699": dict(effect_ids=[1]), "8721": dict(effect_ids=[3])},
                areas={"1951": dict(effect_ids=[2])},
            )
        )
        monsters = {
            "5650": dict(native_abilities=[], initial_state_triples=[8699, 1, 1])
        }
        return tables, monsters

    def test_area_state_grant_slot_and_cycle_are_exact(self):
        tables, monsters = self.sources()
        result = missing_spell_plan(tables, monsters, [5650], {"8331": {}})
        self.assertEqual(result["export_spell_ids"], [8331])
        self.assertEqual(result["absent_installed_casting_ids"], [])
        self.assertEqual(
            result["closures"]["5650"]["missing_definitions"], ["spells:8331"]
        )
        self.assertFalse(result["ownership_changed"])
        self.assertFalse(result["activated"])

    def test_missing_installed_definition_is_reported_not_exported(self):
        tables, monsters = self.sources()
        result = missing_spell_plan(tables, monsters, [5650], {})
        self.assertEqual(result["export_spell_ids"], [])
        self.assertEqual(result["absent_installed_casting_ids"], [8331])

    def test_nested_summon_initial_states_are_followed(self):
        tables, monsters = self.sources()
        tables["states"]["7"] = [8]
        tables["effects"]["8"] = dict(family=307, children=[], references=[5650])
        monsters["5720"] = dict(native_abilities=[], initial_state_triples=[7, 1, 1])
        result = missing_spell_plan(tables, monsters, [5720], {"8331": {}})
        self.assertEqual(result["export_spell_ids"], [8331])
        self.assertIn(5650, result["closures"]["5720"]["closure_profile_ids"])

    def test_unrelated_values_do_not_become_spell_references(self):
        tables, monsters = self.sources()
        tables["effects"]["3"]["references"] = []
        result = missing_spell_plan(tables, monsters, [5650], {"3": {}, "1": {}})
        self.assertEqual(result["export_spell_ids"], [])

    def test_limit_and_unknown_reference_fail_closed(self):
        tables, monsters = self.sources()
        for references, limit in [([5650], True), ([9999], 16)]:
            with self.assertRaises(ValueError):
                missing_spell_plan(tables, monsters, references, {}, limit=limit)
