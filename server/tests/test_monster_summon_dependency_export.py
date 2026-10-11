"""Safety checks for append-only NPC summon dependency imports."""
from copy import deepcopy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from export_monster_summon_dependencies import (
    CATALOG_PATHS,
    assert_preserved,
    compact,
    dependency_closure,
    merge_profiles,
    summon_dependency_scopes,
)


class MonsterSummonDependencyExportTests(unittest.TestCase):
    def scope_fixture(self, mode):
        tables = dict(
            spells={"1": [10], "1948": []},
            states={},
            areas={},
            effects={
                "10": dict(
                    family=307,
                    references=[735],
                    children=[],
                    parameter_samples=[(735, mode)],
                )
            },
        )
        monsters = {
            "735": dict(
                min_level=8,
                max_level=18,
                native_abilities=[dict(spell_id=1948)],
                initial_state_triples=[],
            )
        }
        return tables, monsters

    def test_minimum_descriptor_mode_uses_exact_native_minimum_not_species_maximum(
        self,
    ):
        tables, monsters = self.scope_fixture(-3)
        report = summon_dependency_scopes(tables, monsters, [1])
        scope = report["spell_summon_profiles"]["1"]["735"]
        self.assertEqual(scope["descriptor_levels"], [8])
        self.assertEqual((scope["min_level"], scope["max_level"]), (8, 8))
        self.assertEqual(scope["spell_ids"], [1948])
        self.assertTrue(scope["level_domain_exact"])
        self.assertEqual(report["spell_profile_dependencies"], {"1": [735]})

    def test_direct_caster_level_mode_requires_actual_parent_level_domain(self):
        tables, monsters = self.scope_fixture(-2)
        scope = summon_dependency_scopes(
            tables, monsters, [1], seed_actor_levels={1: [5, 6]}
        )["spell_summon_profiles"]["1"]["735"]
        self.assertEqual(scope["descriptor_levels"], [5, 6])
        self.assertTrue(scope["level_domain_exact"])
        unproven = summon_dependency_scopes(tables, monsters, [1])[
            "spell_summon_profiles"
        ]["1"]["735"]
        self.assertFalse(unproven["level_domain_exact"])

    def test_container_level_union_is_explicitly_unproven(self):
        tables, monsters = self.scope_fixture(-1)
        scope = summon_dependency_scopes(
            tables, monsters, [1], seed_actor_levels={1: [5]}
        )["spell_summon_profiles"]["1"]["735"]
        self.assertFalse(scope["level_domain_exact"])

    def test_nested_summon_cycle_includes_initial_states_and_granted_spell(self):
        tables = dict(
            spells={"1": [10], "2": [20], "3": []},
            states={"7": [70]},
            areas={"8": [80]},
            effects={
                "10": dict(family=307, references=[9], children=[]),
                "20": dict(family=315, references=[8], children=[]),
                "70": dict(family=649, references=[3], children=[]),
                "80": dict(family=307, references=[9], children=[]),
            },
        )
        monsters = {
            "9": dict(
                native_abilities=[dict(spell_id=2)], initial_state_triples=[7, -1, 1]
            )
        }
        result = dependency_closure(tables, monsters, [1])
        self.assertEqual(result["closure_spell_ids"], [1, 2, 3])
        self.assertEqual(result["closure_state_ids"], [7])
        self.assertEqual(result["closure_area_ids"], [8])
        self.assertEqual(result["closure_profile_ids"], [9])
        self.assertEqual(result["missing_definitions"], [])

    def test_missing_profile_is_explicit_failure_evidence(self):
        tables = dict(
            spells={"1": [10]},
            states={},
            areas={},
            effects={"10": dict(family=307, references=[9], children=[])},
        )
        self.assertEqual(
            dependency_closure(tables, {}, [1])["missing_definitions"], ["profiles:9"]
        )

    def test_reference_curves_use_all_native_evaluated_values(self):
        source = dict(
            effects={
                "4": dict(
                    effect_class=307,
                    children=[],
                    parameters=[1.5, 0],
                    parameters_by_level=[[9], [10], [9]],
                )
            }
        )
        self.assertEqual(compact(source)["effects"]["4"]["references"], [9, 10])

    def test_merge_preserves_class_metadata_and_does_not_mutate_inputs(self):
        base = {
            path: dict(
                profiles={
                    "1": dict(abilities=[])
                    if path == CATALOG_PATHS[0]
                    else dict(initial_state_triples=[], fight_properties=[28])
                },
                source="native-class",
            )
            for path in CATALOG_PATHS
        }
        before = deepcopy(base)
        exported = dict(
            profiles={
                "2": dict(
                    abilities=[],
                    initial_state_triples=[7, -1, 1],
                    fight_properties=[15],
                )
            }
        )
        result = merge_profiles(base, exported, dict(original_inputs_stable=True))
        self.assertEqual(base, before)
        for path in CATALOG_PATHS:
            self.assertEqual(
                result[path]["profiles"]["1"], before[path]["profiles"]["1"]
            )
            self.assertEqual(result[path]["source"], "native-class")
            assert_preserved(path, base[path], result[path])

    def test_existing_class_conflict_rejected(self):
        base = {
            path: dict(
                profiles={
                    "2": dict(abilities=[])
                    if path == CATALOG_PATHS[0]
                    else dict(initial_state_triples=[], fight_properties=[])
                }
            )
            for path in CATALOG_PATHS
        }
        exported = dict(
            profiles={
                "2": dict(
                    abilities=[dict(reference=3)],
                    initial_state_triples=[],
                    fight_properties=[],
                )
            }
        )
        with self.assertRaisesRegex(ValueError, "conflicts"):
            merge_profiles(base, exported, dict(original_inputs_stable=True))

    def test_unsealed_added_profiles_rejected(self):
        for path in CATALOG_PATHS:
            with self.assertRaisesRegex(ValueError, "evidence"):
                assert_preserved(path, dict(profiles={}), dict(profiles={"2": {}}))

    def test_removed_class_profile_rejected(self):
        for path in CATALOG_PATHS:
            with self.assertRaisesRegex(ValueError, "existing"):
                assert_preserved(path, dict(profiles={"1": {}}), dict(profiles={}))


if __name__ == "__main__":
    unittest.main()
