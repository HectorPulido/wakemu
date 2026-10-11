"""Rogue actual bomb resource, constructor and attack passive branches."""
import os
import unittest
from unittest.mock import patch
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_summon_handler import NativeSummonHandler

import test_rogue_runtime_pipeline as pipeline


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RogueResourcePassiveTests(unittest.TestCase):
    fixture = pipeline.RogueRuntimePipelineTests.fixture
    cast = pipeline.RogueRuntimePipelineTests.cast
    los = staticmethod(pipeline.RogueRuntimePipelineTests.los)
    summons = staticmethod(pipeline.RogueRuntimePipelineTests.summons)

    @staticmethod
    def states(actor):
        return {row.reference: row.level for row in actor.state_ledger.entries}

    def test_bomber_fan_small_actual_bomb_does_not_receive_off_deck_wp_refund(self):
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = self.fixture((6481,) if equipped else ())
                data, _ = self.cast(data, 7906)
                bomb = self.summons(data[2], (3795, 3796, 3797))[0]
                self.assertLess(self.states(bomb)[7923], 5)
                self.assertEqual(data[2].actors[7].effect_stats[4], 5)
                data, _ = self.cast(data, 6495, bomb.position, action_id=11)
                self.assertEqual(
                    data[2].actors[7].effect_stats[4], 5 if equipped else 6
                )

    def test_artificer_actual_elemental_action_on_owned_bomb_applies_original_state(
        self,
    ):
        helper = pipeline.RogueRuntimePipelineTests()
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = helper.fixture((6482,) if equipped else ())
                caster = data[2].actors[7]
                cell = (caster.position[0] + 1, caster.position[1], caster.position[2])
                data, _ = helper.cast(data, 6473, cell)
                bomb = helper.summons(data[2], (3795, 3796, 3797))[0]
                self.assertNotIn(8057, {s.reference for s in bomb.state_ledger.entries})
                sequence = data[2].sequence
                old_ids = set(data[2].actors)
                data, tx = helper.cast(data, 6473, bomb.position, action_id=11)
                self.assertTrue(any(tx.outcomes))
                receipts = [
                    row
                    for row in data[2].events
                    if row["kind"] == "state_applied"
                    and row["sequence"] > sequence
                    and row["actor_id"] == bomb.id
                    and row["state_id"] == 8057
                ]
                # This occupied branch is417860/417861, not the free-cell,
                # deck-gated395149/395150 constructor branch.
                self.assertEqual([row["level"] for row in receipts], [1])
                self.assertNotIn(
                    8057,
                    {s.reference for s in data[2].actors[bomb.id].state_ledger.entries},
                )
                self.assertEqual(set(data[2].actors), old_ids)
                self.assertEqual(
                    data[2].actors[bomb.id].native_summon_source["controller_id"], 7
                )

    def test_jackpot_close_elemental_constructor_swaps_owner_and_new_bomb(self):
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = self.fixture((7092,) if equipped else ())
                original = data[2].actors[7].position
                cell = (original[0] + 1, original[1], original[2])
                data, _ = self.cast(data, 6473, cell)
                self.assertEqual(
                    data[2].actors[7].position, cell if equipped else original
                )
                events = [
                    row
                    for row in data[2].events
                    if row["kind"] == "state_applied" and row["state_id"] == 8028
                ]
                self.assertEqual(bool(events), equipped)

    def test_surprise_shot_and_master_rogue_have_distinct_actual_attack_consumers(self):
        for passive in (None, 7062, 7091):
            with self.subTest(passive=passive):
                data = self.fixture((passive,) if passive else ())
                data, _ = self.cast(data, 6463, data[2].actors[-7].position)
                # Initial stance application is protected by8093. The first
                # real cast removes that marker at1025; switch stance legally.
                self.assertNotIn(8093, self.states(data[2].actors[7]))
                sequence = data[2].sequence
                owner = data[2].actors[7].position
                data, _ = self.cast(
                    data, 6468, (owner[0], owner[1] + 1, owner[2]), action_id=11
                )
                applied = {
                    row["state_id"]
                    for row in data[2].events
                    if row["kind"] == "state_applied" and row["sequence"] > sequence
                }
                self.assertEqual(8049 in applied, passive == 7062)
                self.assertEqual(bool(applied & {8052, 8053}), passive == 7091)
                if passive == 7091:
                    self.assertNotIn(8051, self.states(data[2].actors[7]))
