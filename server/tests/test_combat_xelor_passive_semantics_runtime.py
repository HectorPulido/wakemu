"""Native Xelor passive numeric contracts through actual published Ready."""
import os
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class XelorPassiveSemanticsRuntimeTests(unittest.TestCase):
    def fixture(self, passives=(), *, actives=(), level=200):
        import test_xelor_runtime_pipeline as helpers

        return helpers.XelorRuntimePipelineTests().fixture(
            level=level, passives=passives, actives=actives
        )

    def test_memory_changes_actual_maximum_wp_and_mp_at_fight_start(self):
        # Native164625 is maximum WP+6; opening312873 is maximum MP-2.
        baseline = self.fixture()[2].actors[7]
        selected = self.fixture((756,))[2].actors[7]
        self.assertEqual(baseline.effect_maxima[4], 12)
        self.assertEqual(selected.effect_maxima[4] - baseline.effect_maxima[4], 6)
        self.assertEqual(selected.max_mp - baseline.max_mp, -2)
        self.assertEqual(selected.mp - baseline.mp, -2)

    def test_assimilation_reduces_actual_maximum_wp_with_baseline_control(self):
        # Native314314 is maximum WP reduction6, not current resource payment.
        baseline = self.fixture()[2].actors[7]
        selected = self.fixture((7196,))[2].actors[7]
        self.assertEqual(selected.effect_maxima[4] - baseline.effect_maxima[4], -6)
        self.assertEqual(selected.effect_stats[4] - baseline.effect_stats[4], -6)
