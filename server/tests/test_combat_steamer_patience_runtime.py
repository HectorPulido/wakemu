"""Patience pays native opening WP and expands SP maximum before threshold."""
import os
import unittest
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerPatienceRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    next_owned_turn = helpers.SteamerRuntimeTests.next_owned_turn

    def test_patience_expands_actual_resource_bound_and_arms_at_real_full_sp(self):
        baseline = self.fixture()[2].actors[7]
        fixture = self.fixture((6933, 6935))
        actor = fixture[2].actors[7]
        self.assertEqual(actor.effect_stats[4], baseline.effect_stats[4] - 2)
        self.assertEqual(actor.effect_maxima[123], baseline.effect_maxima[123])
        initial_maximum = actor.effect_maxima[123]
        self.assertNotIn(7677, {s.reference for s in actor.state_ledger.entries})
        observations = []
        # Reach the actual pre-state maximum through natural regeneration.
        # The level2 state owns the subsequent maximum expansion.
        required_cycles = actor.effect_maxima[123] - actor.effect_stats[123] + 1
        self.assertGreater(required_cycles, 0)
        self.assertLessEqual(required_cycles, 256)
        for _ in range(required_cycles):
            fixture = self.next_owned_turn(fixture)
            actor = fixture[2].actors[7]
            observations.append(
                (
                    actor.effect_stats[123],
                    actor.effect_maxima[123],
                    [
                        (s.reference, s.level)
                        for s in actor.state_ledger.entries
                        if s.reference == 7677
                    ],
                )
            )
            self.assertLessEqual(actor.effect_stats[123], actor.effect_maxima[123])
            if observations[-1][2]:
                break
        self.assertTrue(observations[-1][2], observations)
        self.assertEqual(observations[-1][2][0][1], 2)
        # State7677 itself owns343643; its level2 expands SPmax by2.
        self.assertEqual(actor.effect_maxima[123], initial_maximum + 2)
