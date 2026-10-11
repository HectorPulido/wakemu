"""Actual out-of-turn AP/MP maximum gains on an owned companion."""
import os
import unittest

import test_aniripsa_grant_summon_pipeline as turn_helpers
import test_enutrof_runtime as enutrof_helpers
from wakfu_server.combat_diagnostics import combat_diagnostic_scope


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class ResourceTurnGainControlTests(unittest.TestCase):
    def test_actual_treasure_gain_survives_companion_first_turn_start(self):
        fixture = enutrof_helpers.EnutrofRuntimeTests().fixture(
            passives=(2039, 8280), target_distance=3
        )
        fight = fixture[2]
        companion = next(
            actor
            for actor in fight.actors.values()
            if getattr(actor, "native_summon_source", None)
        )
        before = (companion.ap, companion.max_ap, companion.mp, companion.max_mp)
        trace = []
        with combat_diagnostic_scope(lambda **row: trace.append(row), limit=8192):
            turn_helpers.AniripsaGrantSummonPipelineTests().end_current_turn(
                fight, fixture
            )

        companion = fight.actors[companion.id]
        after_gain = (companion.ap, companion.max_ap, companion.mp, companion.max_mp)
        completed = {
            row.get("effect_reference")
            for row in trace
            if row.get("status") == "completed"
        }
        self.assertTrue({386213, 386214} <= completed, trace)
        self.assertEqual(after_gain[1], before[1] + 1)
        self.assertEqual(after_gain[3], before[3] + 1)
        self.assertIn(after_gain[0] - before[0], (0, 1))
        self.assertIn(after_gain[2] - before[2], (0, 1))

        helper = turn_helpers.AniripsaGrantSummonPipelineTests()
        for _ in range(24):
            if fight.current.id == companion.id:
                break
            helper.end_current_turn(fight, fixture)
        self.assertEqual(fight.current.id, companion.id)
        current_turn = fight.actors[companion.id]
        self.assertEqual(
            (
                current_turn.ap,
                current_turn.max_ap,
                current_turn.mp,
                current_turn.max_mp,
            ),
            after_gain,
        )


if __name__ == "__main__":
    unittest.main()
