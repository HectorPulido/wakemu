"""Real passive-owned Microbot casting variants, preserving native prerequisites."""
import os
import unittest
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerPassiveCastingRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast

    def test_transport_and_winding_paths_select_real_microbot_range_variants(self):
        cases = {(): (1, 7), (6930,): (1, 3), (6926,): (1, 7), (6926, 6930): (1, 3)}
        baseline_range = None
        for passives, expected in cases.items():
            with self.subTest(passives=passives):
                fixture = self.fixture(passives)
                states = {
                    s.reference for s in fixture[2].actors[7].state_ledger.entries
                }
                self.assertNotIn(7745, states)
                # 7745 belongs to the full-WP 6925 branch, not 6926.
                # Flags expose the selected definition range, before stat93.
                # 6926 subtracts range through root343871;6930 selects
                # a fixed, unmodifiable definition range.
                current_range = fixture[2].actors[7].effect_stats.get(93, 0)
                if not passives:
                    baseline_range = current_range
                self.assertEqual(
                    current_range, baseline_range - (2 if 6926 in passives else 0)
                )
                born = self.cast(fixture, 7008)
                flags = born.plan["native_casting_flags"]
                self.assertEqual((flags["minimum"], flags["maximum"]), expected)
                self.assertEqual(
                    len(born.fight.native_microbot_networks[7]["microbot_ids"]), 1
                )
