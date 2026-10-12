import unittest
import export_monster_summon_dependencies as exporter
import extract_monster_combat_inventory as inventory


class TriggeredClosureTests(unittest.TestCase):
    def tables(self):
        return exporter.compact(
            dict(
                spells={"1": {"effect_ids": [10]}, "4749": {"effect_ids": [151351]}},
                effects={
                    "10": {
                        "effect_class": 426,
                        "parameters_by_level": [[4749], [4749]],
                        "children": [],
                    },
                    "151351": {
                        "effect_class": 349,
                        "parameters_by_level": [],
                        "children": [151352],
                    },
                    "151352": {
                        "effect_class": 307,
                        "parameters_by_level": [[3537, 0, 1]],
                        "children": [],
                    },
                },
            )
        )

    def test_triggered_spell_is_forward_dependency_and_reaches_native_profile(self):
        result = exporter.dependency_closure(
            self.tables(),
            {"3537": {"native_abilities": [], "initial_state_triples": []}},
            [1],
        )
        self.assertEqual(result["closure_spell_ids"], [1, 4749])
        self.assertEqual(result["closure_profile_ids"], [3537])
        self.assertEqual(result["missing_definitions"], [])

    def test_missing_triggered_spell_is_reported_not_silently_covered(self):
        tables = self.tables()
        del tables["spells"]["4749"]
        result = exporter.dependency_closure(tables, {}, [1])
        self.assertIn("spells:4749", result["missing_definitions"])

    def test_cycles_terminate_and_original_spell_grant_operand_is_preserved(self):
        tables = self.tables()
        tables["effects"]["151352"] = {"family": 649, "children": [], "references": [1]}
        result = exporter.dependency_closure(tables, {}, [1])
        self.assertEqual(result["closure_spell_ids"], [1, 4749])
        grant = exporter.compact(
            {
                "effects": {
                    "2": {
                        "effect_class": 649,
                        "parameters_by_level": [[99, 7, 444]],
                        "children": [],
                    }
                }
            }
        )
        self.assertEqual(grant["effects"]["2"]["references"], [444])

    def test_inventory_follows_real_trigger_operand_and_reports_missing(self):
        result = inventory.dependency_closure(
            [1],
            [],
            {"1": {"levels": [[0, 0, [10]]]}},
            {},
            {
                "10": {
                    "effect_class": 426,
                    "children": [],
                    "parameters_by_level": [[4749]],
                }
            },
        )
        self.assertEqual(result["spell_ids"], [1, 4749])
        self.assertIn("spell:4749", result["missing_definitions"])
        self.assertEqual(
            result["candidate_links"],
            [dict(effect_id=10, family=426, target_kind="spell", reference=4749)],
        )


if __name__ == "__main__":
    unittest.main()
