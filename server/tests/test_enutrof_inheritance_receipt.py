"""Actual Herencia treasure-end AP/MP transfer to its owned companion."""
import os
import unittest
import test_enutrof_runtime as enutrof
import test_aniripsa_grant_summon_pipeline as turns
from wakfu_server.combat_diagnostics import combat_diagnostic_scope


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native integration opt-in"
)
class EnutrofInheritanceReceiptTests(unittest.TestCase):
    fixture = enutrof.EnutrofRuntimeTests.fixture

    def test_real_treasure_end_transfers_one_ap_mp_to_owned_companion(self):
        for passives in ((2039,), (2039, 8280)):
            with self.subTest(passives=passives):
                data = self.fixture(passives=passives, target_distance=3)
                fight = data[2]
                companion = next(
                    a
                    for a in fight.actors.values()
                    if getattr(a, "native_summon_source", None)
                )
                treasure = sum(
                    s.level
                    for s in fight.actors[7].state_ledger.entries
                    if s.reference == 8552
                )
                self.assertEqual(treasure, 1)
                before = (companion.max_ap, companion.max_mp)
                trace = []
                with combat_diagnostic_scope(lambda **r: trace.append(r), limit=8192):
                    turns.AniripsaGrantSummonPipelineTests().end_current_turn(
                        fight, data
                    )
                completed = {
                    r.get("effect_reference")
                    for r in trace
                    if r.get("status") == "completed"
                }
                companion = fight.actors[companion.id]
                if 8280 in passives:
                    self.assertTrue({386213, 386214} <= completed)
                    self.assertEqual(
                        (companion.max_ap, companion.max_mp),
                        (before[0] + 1, before[1] + 1),
                    )
                else:
                    self.assertFalse({386213, 386214} & completed)
                    self.assertEqual((companion.max_ap, companion.max_mp), before)
