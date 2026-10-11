"""Native Enutrof passive branches through actual owned casts and boundaries."""
import os
import unittest

import test_enutrof_runtime as enutrof
import test_aniripsa_grant_summon_pipeline as turns
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.fight_checkpoint_store import snapshot


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native integration opt-in"
)
class EnutrofPassiveBranchTests(unittest.TestCase):
    fixture = enutrof.EnutrofRuntimeTests.fixture
    cast = enutrof.EnutrofRuntimeTests.cast

    @staticmethod
    def levels(actor, reference):
        return sum(
            row.level
            for row in actor.state_ledger.entries
            if row.reference == reference
        )

    @staticmethod
    def update(data, transaction):
        return (*data[:2], transaction.fight, *data[3:])

    def test_codicia_extracts_converted_deposit_and_bursatil_defers_reward(self):
        # 2063's actual casting table admits207 only with5071. Its native
        # 386199 branch rewards MP/healing normally,8553 when5059 is equipped.
        for passives in ((), (5071,), (5071, 5059)):
            with self.subTest(passives=passives):
                data = self.fixture(passives=passives, actives=(2026,))
                converted = self.cast(data, 2026, data[2].actors[7].position)
                data = self.update(data, converted)
                rows = [
                    r
                    for r in data[2].native_effect_areas.values()
                    if r["owner_id"] == 7
                    and r["reference"] == 207
                    and 1
                    <= sum(
                        abs(r["cell"][i] - data[2].actors[7].position[i])
                        for i in (0, 1)
                    )
                    <= 5
                ]
                self.assertTrue(rows, "Actual conversion must create reachable207")
                deposit = min(rows, key=lambda r: r["uid"])
                before = snapshot(data[2])
                if not passives:
                    with self.assertRaises(ValueError):
                        self.cast(data, 2063, tuple(deposit["cell"]), action_id=4)
                    self.assertEqual(snapshot(data[2]), before)
                    continue
                actor = data[2].actors[7]
                tx = self.cast(data, 2063, tuple(deposit["cell"]), action_id=4)
                self.assertNotIn(deposit["uid"], tx.fight.native_effect_areas)
                after = tx.fight.actors[7]
                self.assertEqual(self.levels(after, 8553), 1 if 5059 in passives else 0)
                self.assertEqual(
                    after.max_mp - actor.max_mp, 0 if 5059 in passives else 1
                )
                if 5059 in passives:
                    # Real next1001 consumes deferred8553; no direct event replay.
                    updated = self.update(data, tx)
                    turns.AniripsaGrantSummonPipelineTests().next_player_turn(
                        tx.fight, updated
                    )
                    self.assertEqual(self.levels(tx.fight.actors[7], 8553), 0)

    def test_perfortanker_changes_actual_bestiality_end_boundary_branch(self):
        for passive in (None, 5075):
            with self.subTest(passive=passive):
                data = self.fixture(passives=() if passive is None else (passive,))
                tx = self.cast(data, 2038, data[2].actors[7].position)
                data = self.update(data, tx)
                before = dict(data[2].actors[7].effect_stats)
                trace = []
                with combat_diagnostic_scope(
                    lambda **row: trace.append(row), limit=8192
                ):
                    turns.AniripsaGrantSummonPipelineTests().end_current_turn(
                        data[2], data
                    )
                self.assertEqual(self.levels(data[2].actors[7], 8572), 1)
                completed = {
                    r.get("effect_reference")
                    for r in trace
                    if r.get("status") == "completed"
                }
                expected, forbidden = (386209, 385058) if passive else (385058, 386209)
                self.assertIn(expected, completed)
                self.assertNotIn(forbidden, completed)
                self.assertNotEqual(dict(data[2].actors[7].effect_stats), before)

    def test_risk_insurance_turns_real_treasure_into_armor(self):
        for passives in ((2039,), (2039, 8276)):
            with self.subTest(passives=passives):
                data = self.fixture(passives=passives)
                actor = data[2].actors[7]
                self.assertGreater(
                    self.levels(actor, 8552),
                    0,
                    "Actual2039 first1001 must grant treasure",
                )
                before = dict(actor.effect_stats)
                trace = []
                with combat_diagnostic_scope(
                    lambda **row: trace.append(row), limit=8192
                ):
                    turns.AniripsaGrantSummonPipelineTests().end_current_turn(
                        data[2], data
                    )
                completed = {
                    r.get("effect_reference")
                    for r in trace
                    if r.get("status") == "completed"
                }
                if 8276 in passives:
                    self.assertIn(386084, completed)
                    self.assertEqual(self.levels(data[2].actors[7], 8552), 0)
                    self.assertNotEqual(dict(data[2].actors[7].effect_stats), before)
                else:
                    self.assertNotIn(386084, completed)
                    self.assertGreater(self.levels(data[2].actors[7], 8552), 0)
