"""Preparation utility consumes only measured, capped owned prerequisites."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_ai.planning.feature_values import DEFAULT_FEATURE_WEIGHTS
from wakfu_ai.planning.scoring import evaluate
from wakfu_ai.planning.tactical import DEFAULT_WEIGHTS


class OwnedStateProgressUtilityTests(unittest.TestCase):
    def state(self, progress, ap=6):
        return dict(
            actors={
                1: dict(
                    id=1,
                    team=1,
                    hp=10,
                    max_hp=10,
                    armor=0,
                    ap=ap,
                    mp=3,
                    wp=0,
                    position=(0, 0, 0),
                )
            },
            threat=0,
            position=0,
            uncertainty=0,
            features={"owned_state_progress": progress},
        )

    def test_actual_progress_outweighs_small_producer_payment(self):
        root, produced = self.state(0), self.state(1, ap=3)
        score, components, _, _ = evaluate(
            root, produced, 1, DEFAULT_WEIGHTS, {}, DEFAULT_FEATURE_WEIGHTS
        )
        self.assertGreater(score, 0)
        self.assertEqual(components["feature:owned_state_progress"], 1)
        self.assertAlmostEqual(components["resources"], -0.3)

    def test_existing_or_capped_progress_is_not_rewarded_again(self):
        root, repeat = self.state(30), self.state(30, ap=3)
        score, components, _, _ = evaluate(
            root, repeat, 1, DEFAULT_WEIGHTS, {}, DEFAULT_FEATURE_WEIGHTS
        )
        self.assertLess(score, 0)
        self.assertEqual(components["feature:owned_state_progress"], 0)

    def test_unrelated_state_without_measurement_has_no_utility(self):
        root, after = self.state(0), self.state(0, ap=3)
        score, _, _, _ = evaluate(
            root, after, 1, DEFAULT_WEIGHTS, {}, DEFAULT_FEATURE_WEIGHTS
        )
        self.assertLess(score, 0)


if __name__ == "__main__":
    unittest.main()
