"""World birth/publication fences consume externally prepared lifecycle requests."""

import unittest
from test_monster_maturation_coordination import WorldCoordinationFixture


class ReproductionCoordinationTests(WorldCoordinationFixture, unittest.TestCase):
    kind = "reproduction"

    def test_policy_is_read_outside_fences_and_refreshes_next_unpinned_proposal(self):
        self.patches()
        observed = []

        def policy(_store):
            self.assertFalse(self.groups.lock.held)
            self.assertFalse(self.harvests.lock.held)
            observed.append(self.configuration["interval_ms"])
            return dict(self.configuration)

        self.policy.side_effect = policy
        self.apply()
        self.configuration["interval_ms"] = 60001
        self.apply()
        self.assertEqual(observed, [60000, 60001])
        self.assertEqual(self.policy.call_count, 2)
        self.assertEqual(self.attempt.call_count, 2)
