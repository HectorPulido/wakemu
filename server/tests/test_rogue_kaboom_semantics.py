"""Native Kaboom recipient split on an actual owned bomb explosion."""
import os
import unittest
from unittest.mock import patch
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_summon_handler import NativeSummonHandler

import test_rogue_runtime_pipeline as pipeline


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RogueKaboomSemanticsTests(unittest.TestCase):
    fixture = pipeline.RogueRuntimePipelineTests.fixture
    cast = pipeline.RogueRuntimePipelineTests.cast
    los = staticmethod(pipeline.RogueRuntimePipelineTests.los)
    summons = staticmethod(pipeline.RogueRuntimePipelineTests.summons)

    def test_real_detonation_splits_friendly_and_enemy_receipts(self):
        helper = pipeline.RogueRuntimePipelineTests()
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = helper.fixture((7064,) if equipped else ())
                data, _ = helper.cast(data, 7906)
                bomb = helper.summons(data[2], (3795, 3796, 3797))[0]
                sequence = data[2].sequence
                lineage = []
                original = EffectDispatcher.execute

                def observe(dispatcher, invocation, *args, **kwargs):
                    result = original(dispatcher, invocation, *args, **kwargs)
                    if invocation.reference == 418252 and result:
                        lineage.append(dict(invocation.native_trigger_context))
                    return result

                with patch.object(EffectDispatcher, "execute", observe):
                    data, tx = helper.cast(data, 6495, bomb.position, action_id=11)
                self.assertTrue(any(tx.outcomes))
                # Native nonselective7923 retains both authored2145 roots.
                # Each distinct eXc emits2240 and adds exactly one Dinamita rank.
                self.assertEqual(
                    [row["generic_effect"] for row in lineage], [358246, 367586]
                )
                self.assertEqual(
                    [row["native_definition_variant"] for row in lineage], [0, 1]
                )
                self.assertEqual(len({row["uid"] for row in lineage}), 2)
                for source in lineage:
                    self.assertEqual(source["target_id"], bomb.id)
                    self.assertEqual(source["native_container"]["state_id"], 7923)
                    self.assertEqual(tuple(source["event_ids"]), (0, 192, 2240))
                    self.assertTrue(source["native_events_verified"])
                self.assertEqual(data[2].actors[bomb.id].hp, 0)
                receipts = [
                    row
                    for row in data[2].events
                    if row["kind"] == "state_applied" and row["sequence"] > sequence
                ]
                self.assertEqual(
                    [
                        row["level"]
                        for row in receipts
                        if row["actor_id"] == 7 and row["state_id"] == 9367
                    ],
                    [1, 2],
                )
                self.assertFalse(
                    any(row["state_id"] in (9310, 8050) for row in receipts)
                )
                self.assertEqual(
                    [
                        s.level
                        for s in data[2].actors[7].state_ledger.entries
                        if s.reference == 9367
                    ],
                    [2],
                )
