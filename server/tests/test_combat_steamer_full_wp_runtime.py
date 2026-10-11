"""Full-WP passive activates only after real natural regeneration."""
import os
import unittest
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerFullWpRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    next_owned_turn = helpers.SteamerRuntimeTests.next_owned_turn

    def test_full_wp_guard_installs_native_marker_and_armor_given_bonus(self):
        for passive in (None, 6925):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                actor = fixture[2].actors[7]
                before = actor.effect_stats.get(120, 0)
                self.assertNotIn(
                    7745, {s.reference for s in actor.state_ledger.entries}
                )
                for _ in range(4):
                    fixture = self.next_owned_turn(fixture)
                actor = fixture[2].actors[7]
                self.assertEqual(actor.effect_stats[4], actor.effect_maxima[4])
                self.assertEqual(
                    7745 in {s.reference for s in actor.state_ledger.entries},
                    passive == 6925,
                )
                self.assertEqual(
                    actor.effect_stats.get(120, 0) - before,
                    30 if passive == 6925 else 0,
                )
