"""Dependency exports preserve native eZl defaults without inventing authority."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from export_monster_summon_dependencies import summon_dependency_scopes


class SummonDefaultLevelModeTests(unittest.TestCase):
    def scope(self, parameters):
        return summon_dependency_scopes(
            dict(
                spells={"1": [10], "2": []},
                states={},
                areas={},
                effects={
                    "10": dict(
                        family=307,
                        references=[9],
                        children=[],
                        parameter_samples=[parameters],
                    )
                },
            ),
            {
                "9": dict(
                    min_level=3,
                    max_level=7,
                    native_abilities=[dict(spell_id=2)],
                    initial_state_triples=[],
                )
            },
            [1],
            seed_actor_levels={1: [5]},
        )["spell_summon_profiles"]["1"]["9"]

    def test_omitted_mode_matches_explicit_container_default(self):
        self.assertEqual(self.scope((9,)), self.scope((9, -1)))

    def test_default_never_promotes_unknown_container_domain_to_exact(self):
        scope = self.scope((9,))
        self.assertFalse(scope["level_domain_exact"])
        self.assertEqual(scope["level_modes"], [-1])

    def test_missing_reference_still_rejects(self):
        with self.assertRaisesRegex(ValueError, "Missing original summon reference"):
            self.scope(())


if __name__ == "__main__":
    unittest.main()
