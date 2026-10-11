"""Native mode-zero samples remain evidence but construct no descriptor."""
import unittest
import test_monster_summon_dependency_export as fixture
from export_monster_summon_dependencies import summon_dependency_scopes


class SummonNonexecutingSampleTests(unittest.TestCase):
    def setUp(self):
        (
            self.tables,
            self.monsters,
        ) = fixture.MonsterSummonDependencyExportTests().scope_fixture(0)

    def scope(self):
        return summon_dependency_scopes(self.tables, self.monsters, [1])[
            "spell_summon_profiles"
        ]["1"]["735"]

    def test_mixed_zero_and_positive_samples_preserve_zero_witness(self):
        self.tables["effects"]["10"]["parameter_samples"].append((735, 8))
        scope = self.scope()
        self.assertEqual(scope["descriptor_levels"], [8])
        self.assertEqual(scope["level_modes"], [0, 8])
        self.assertEqual(
            scope["nonexecuting_samples"],
            [
                dict(
                    effect_id=10,
                    parameters=[735, 0],
                    level_mode=0,
                    reason="native_invalid_level_mode_no_summon",
                    source="eZl.C.227_249",
                )
            ],
        )
        self.assertTrue(scope["level_domain_exact"])

    def test_all_nonexecuting_is_not_readiness_or_invented_level_zero(self):
        scope = self.scope()
        self.assertEqual(scope["descriptor_levels"], [])
        self.assertIsNone(scope["min_level"])
        self.assertIsNone(scope["max_level"])
        self.assertFalse(scope["level_domain_exact"])

    def test_nested_closure_keeps_nonexecuting_dependency_evidence(self):
        self.tables["spells"]["1948"] = [11]
        self.tables["effects"]["10"]["parameter_samples"] = [(735, -3)]
        self.tables["effects"]["11"] = dict(
            family=307, references=[736], children=[], parameter_samples=[(736, 0)]
        )
        self.tables["spells"]["1949"] = []
        self.monsters["736"] = dict(
            min_level=2,
            max_level=3,
            native_abilities=[dict(spell_id=1949)],
            initial_state_triples=[],
        )
        report = summon_dependency_scopes(self.tables, self.monsters, [1])
        self.assertEqual(report["spell_profile_dependencies"]["1"], [735, 736])
        nested = report["spell_summon_profiles"]["1"]["736"]
        self.assertEqual(nested["nonexecuting_samples"][0]["effect_id"], 11)
        self.assertFalse(nested["level_domain_exact"])
