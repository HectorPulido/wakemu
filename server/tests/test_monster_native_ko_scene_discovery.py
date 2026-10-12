"""Only required actual target KO plus non-enemy predicates request KO scenes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_pending_scenarios import native_ko_ally_recipe, requires_non_enemy_target


class NativeKOSceneDiscoveryTests(unittest.TestCase):
    def test_actual_4086_multiline_criterion_requests_real_owned_ko_scene(self):
        criterion = (
            'not IsEnnemy()\r\nand IsOffPlay("target") and not HasState(1144, "target") '
            'and not HasFightProperty("target", 66)'
        )
        self.assertEqual(native_ko_ally_recipe(criterion), "knocked_out_ally")
        self.assertTrue(requires_non_enemy_target(criterion))

    def test_required_nested_and_accepts_without_certifying_other_requirements(self):
        self.assertEqual(
            native_ko_ally_recipe(
                'HasState(12, "caster") and (IsOffPlay("target") and not IsEnnemy())'
            ),
            "knocked_out_ally",
        )

    def test_optional_or_wrong_actor_negation_and_malformed_do_not_request_ko(self):
        for criterion in (
            'not IsEnnemy() or IsOffPlay("target")',
            'not IsEnnemy() and (IsOffPlay("target") or HasState(12, "target"))',
            '(not IsEnnemy() or IsCarried()) and IsOffPlay("target")',
            'not IsEnnemy() and not IsOffPlay("target")',
            'not IsEnnemy() and IsOffPlay("caster")',
            'not IsEnnemy() and IsOffPlay(target="target")',
            'not IsEnnemy() and Other.IsOffPlay("target")',
            "not IsEnnemy()",
            'IsOffPlay("target")',
            None,
            "",
            "not IsEnnemy(",
        ):
            with self.subTest(criterion=criterion):
                self.assertIsNone(native_ko_ally_recipe(criterion))


if __name__ == "__main__":
    unittest.main()
