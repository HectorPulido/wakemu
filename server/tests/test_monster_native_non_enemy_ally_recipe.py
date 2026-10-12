"""Native non-enemy criteria request scenes without changing casting rules."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_pending_scenarios import native_ally_recipe, requires_non_enemy_target


class NativeNonEnemyAllyRecipeTests(unittest.TestCase):
    def test_native_non_enemy_spell_without_supportive_tags_gets_ordinary_ally(self):
        recipe = native_ally_recipe(
            2830,
            1,
            dict(tags=["special", "state", "unknown"]),
            criterion="not IsEnnemy()",
        )
        self.assertEqual(recipe["opponent"], dict(reference=2830, level=1, team=1))
        self.assertEqual(set(recipe), {"kind", "opponent", "discovery"})
        self.assertEqual(recipe["kind"], "native_opponent")

    def test_required_conjunction_recurses_without_claiming_remaining_terms(self):
        self.assertTrue(
            requires_non_enemy_target(
                'HasState(123, "target") and (not IsEnnemy() and not IsCarried())'
            )
        )
        self.assertIsNotNone(
            native_ally_recipe(
                2831,
                17,
                dict(tags=["damage"]),
                criterion='not IsEnnemy() and HasState(123, "target")',
            )
        )

    def test_optional_or_and_different_selector_do_not_trigger_discovery(self):
        for criterion in (
            "not IsEnnemy() or IsCarried()",
            "not (IsEnnemy() and IsCarried())",
            "not not IsEnnemy()",
            'not IsEnnemy("caster")',
            "not IsEnnemy(target=True)",
            "not Other.IsEnnemy()",
            "IsEnnemy() and not IsTargetCellFree() and not IsCarried()",
            "not IsEnnemy(",
            "",
            None,
        ):
            with self.subTest(criterion=criterion):
                self.assertFalse(requires_non_enemy_target(criterion))
                self.assertIsNone(
                    native_ally_recipe(
                        2828,
                        1,
                        dict(tags=["damage"]),
                        criterion=criterion,
                    )
                )

    def test_native_ally_only_root_requests_scene_without_cast_criterion(self):
        effect = {"native_target_selector": {"class": "fcE", "mask": 5}}
        recipe = native_ally_recipe(
            2831, 1, {"tags": ["special"]}, root_effects=[effect]
        )
        self.assertEqual(recipe["opponent"], dict(reference=2831, level=1, team=1))
        for mask in (1, 2, 9):
            with self.subTest(mask=mask):
                self.assertIsNone(
                    native_ally_recipe(
                        2831,
                        1,
                        {},
                        root_effects=[
                            {"native_target_selector": {"class": "fcE", "mask": mask}}
                        ],
                    )
                )
        with self.assertRaises(ValueError):
            native_ally_recipe(2831, 1, {}, root_effects=[{}])

    def test_real_native_identity_bounds_remain_required(self):
        for reference, level in ((0, 1), (2830, 0), (True, 1), (2830, True)):
            with self.subTest(reference=reference, level=level):
                with self.assertRaisesRegex(ValueError, "Invalid native ally"):
                    native_ally_recipe(reference, level, {}, criterion="not IsEnnemy()")


if __name__ == "__main__":
    unittest.main()
