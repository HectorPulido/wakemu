"""Native994 fixed-profile closure without guessed contextual target levels."""
import json
from pathlib import Path
import unittest
from export_monster_summon_dependencies import (
    compact,
    dependency_closure,
    summon_dependency_scopes,
)


class TargetCopyDependencyExportTests(unittest.TestCase):
    def fixture(self):
        source = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "monster_target_copy2349_native.json"
            ).read_text()
        )
        monsters = {"2349": source["native_monster_profile"]}
        document = dict(
            spells={"11": {"effect_ids": [9941, 3071]}},
            effects={
                "9941": dict(
                    effect_class=994, children=[], parameters_by_level=[[100]]
                ),
                "3071": dict(
                    effect_class=307, children=[], parameters_by_level=[[2349, 20]]
                ),
            },
        )
        return compact(document), monsters

    def test_fixed_profile_edge_is_typed_and_preserves_existing307_edge(self):
        tables, monsters = self.fixture()
        report = dependency_closure(tables, monsters, [11])
        self.assertEqual(report["closure_profile_ids"], [2349])
        self.assertEqual(report["missing_definitions"], [])
        self.assertIn(
            dict(effect_reference=3071, profile_id=2349), report["effect_profile_edges"]
        )
        self.assertIn(
            dict(
                effect_reference=9941,
                profile_id=2349,
                family=994,
                edge_type="native_fixed_profile",
                producer="eZq.eZn.faB.eHI.cmY",
            ),
            report["effect_profile_edges"],
        )

    def test_contextual_target_level_stays_unknown_even_with_parent_level_domain(self):
        tables, monsters = self.fixture()
        report = summon_dependency_scopes(
            tables, monsters, [11], seed_actor_levels={11: [1, 2]}
        )
        scope = report["spell_summon_profiles"]["11"]["2349"]
        self.assertEqual(scope["descriptor_levels"], [20])
        self.assertFalse(scope["level_domain_exact"])
        self.assertEqual(scope["contextual_target_levels"][0]["finite_domain"], None)
        from monster_summon_book_source import qualified_empty_book

        self.assertTrue(qualified_empty_book(2349, scope["native_empty_book_source"]))

    def test_fixed_profile_source_cannot_be_substituted(self):
        tables, monsters = self.fixture()
        tables["effects"]["9941"]["references"] = [2382]
        with self.assertRaisesRegex(ValueError, "fixed-profile source"):
            dependency_closure(tables, monsters, [11])
