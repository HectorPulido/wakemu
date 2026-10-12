"""Native wrapper reuse proves spell container domains, never actor bounds."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from export_monster_summon_dependencies import compact, summon_dependency_scopes


class SummonContainerLevelTests(unittest.TestCase):
    def fixture(self):
        tables = dict(
            spells={"1": [10], "2": []},
            states={},
            areas={},
            spell_level_roots={"1": {"7": [10], "11": [10]}},
            effects={
                "10": dict(
                    family=349, children=[11], references=[], native_effect_flags=[17]
                ),
                "11": dict(
                    family=341, children=[12], references=[], native_effect_flags=[17]
                ),
                "12": dict(
                    family=307,
                    children=[],
                    references=[9],
                    parameter_samples=[(9,)],
                    parameter_samples_by_level={"7": [9], "11": [9]},
                ),
            },
        )
        monsters = {
            "9": dict(
                min_level=93,
                max_level=100,
                native_abilities=[dict(spell_id=2)],
                initial_state_triples=[],
            )
        }
        return tables, monsters

    def scope(self, tables=None, contexts=None):
        source, monsters = self.fixture()
        return summon_dependency_scopes(
            source if tables is None else tables,
            monsters,
            [1],
            seed_actor_levels={1: [50, 100]},
            seed_container_contexts={1: contexts} if contexts is not None else None,
        )["spell_summon_profiles"]["1"]["9"]

    def test_nested_wrappers_use_exact_spell_levels_not_actor_or_species_levels(self):
        scope = self.scope(contexts=[dict(container_level=7), dict(container_level=11)])
        self.assertEqual(scope["descriptor_levels"], [7, 11])
        self.assertTrue(scope["level_domain_exact"])

    def test_actor_domain_alone_cannot_establish_container_levels(self):
        scope = self.scope()
        self.assertFalse(scope["level_domain_exact"])
        self.assertEqual(scope["descriptor_levels"], [])

    def test_fresh_child_context_drops_override_without_native_transmission_flag(self):
        scope = self.scope(contexts=[dict(container_level=7, level_override=11)])
        self.assertEqual(scope["descriptor_levels"], [7])
        self.assertTrue(scope["level_domain_exact"])

    def test_native_transmission_flag_carries_resolved_override_through_both_wrappers(
        self,
    ):
        tables, _ = self.fixture()
        for effect in ("10", "11"):
            tables["effects"][effect]["native_effect_flags"] = [16, 17]
        scope = self.scope(tables, [dict(container_level=7, level_override=11)])
        self.assertEqual(scope["descriptor_levels"], [11])
        self.assertTrue(scope["level_domain_exact"])

    def test_state_application_does_not_reuse_spell_container_level(self):
        tables, _ = self.fixture()
        tables["effects"]["10"] = dict(family=304, children=[], references=[8])
        tables["states"]["8"] = [12]
        scope = self.scope(tables, [dict(container_level=7)])
        self.assertEqual(scope["descriptor_levels"], [])
        self.assertFalse(scope["level_domain_exact"])

    def test_unsupported_wrapper_cannot_borrow_known_ancestor_domain(self):
        tables, _ = self.fixture()
        tables["effects"]["11"]["family"] = 330
        scope = self.scope(tables, [dict(container_level=7)])
        self.assertFalse(scope["level_domain_exact"])
        self.assertEqual(scope["descriptor_levels"], [])

    def test_unknown_shared_path_taints_otherwise_known_summon(self):
        tables, _ = self.fixture()
        tables["effects"]["10"]["children"].append(13)
        tables["effects"]["13"] = dict(family=304, children=[], references=[8])
        tables["states"]["8"] = [12]
        scope = self.scope(tables, [dict(container_level=7)])
        self.assertFalse(scope["level_domain_exact"])
        self.assertEqual(scope["descriptor_levels"], [7])

    def test_missing_evaluated_parameter_level_keeps_container_domain_unproven(self):
        tables, _ = self.fixture()
        del tables["effects"]["12"]["parameter_samples_by_level"]["11"]
        scope = self.scope(tables, [dict(container_level=7), dict(container_level=11)])
        self.assertEqual(scope["descriptor_levels"], [7])
        self.assertFalse(scope["level_domain_exact"])

    def test_varying_native_profile_parameter_uses_only_its_evaluated_levels(self):
        tables, monsters = self.fixture()
        effect = tables["effects"]["12"]
        effect["references"] = [9, 8]
        effect["parameter_samples"] = [(9,), (8,)]
        effect["parameter_samples_by_level"]["11"] = [8]
        monsters["8"] = dict(monsters["9"])
        scopes = summon_dependency_scopes(
            tables,
            monsters,
            [1],
            seed_container_contexts={
                1: [dict(container_level=7), dict(container_level=11)]
            },
        )["spell_summon_profiles"]["1"]
        self.assertEqual(scopes["9"]["descriptor_levels"], [7])
        self.assertEqual(scopes["8"]["descriptor_levels"], [11])
        self.assertTrue(scopes["9"]["level_domain_exact"])
        self.assertTrue(scopes["8"]["level_domain_exact"])

    def test_unavailable_native_spell_level_rejects_context(self):
        with self.assertRaisesRegex(
            ValueError, "Unproven native spell container context"
        ):
            self.scope(contexts=[dict(container_level=8)])

    def test_compaction_keeps_distinct_level_roots_and_raw_transmission_flag(self):
        tables = compact(
            dict(
                spells={
                    "1": dict(level_zero_roots=[3], levels=[[0, 1, [10]], [0, 1, [11]]])
                },
                effects={
                    "10": dict(
                        effect_class=349, native_effect_flags=[16, 17], children=[12]
                    )
                },
            )
        )
        self.assertEqual(
            tables["spell_level_roots"]["1"], {"0": [3], "1": [10], "2": [11]}
        )
        self.assertEqual(tables["effects"]["10"]["native_effect_flags"], [16, 17])


if __name__ == "__main__":
    unittest.main()
