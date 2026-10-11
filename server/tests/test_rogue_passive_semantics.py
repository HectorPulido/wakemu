"""Source-qualified Rogue passive branches with actual owned action controls."""
import os
import unittest

import test_rogue_runtime_pipeline as pipeline
import test_aniripsa_grant_summon_pipeline as turns


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RoguePassiveSemanticsTests(unittest.TestCase):
    fixture = pipeline.RogueRuntimePipelineTests.fixture
    cast = pipeline.RogueRuntimePipelineTests.cast
    los = staticmethod(pipeline.RogueRuntimePipelineTests.los)
    summons = staticmethod(pipeline.RogueRuntimePipelineTests.summons)
    powder = staticmethod(pipeline.RogueRuntimePipelineTests.powder)

    @staticmethod
    def levels(actor, reference):
        return [
            row.level
            for row in actor.state_ledger.entries
            if row.reference == reference
        ]

    def test_tymobum_adds_two_original_robot_mp_with_unequipped_control(self):
        values = {}
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = self.fixture((6479,) if equipped else ())
                data, _ = self.cast(data, 7905)
                robot = self.summons(data[2], (1236,))[0]
                values[equipped] = robot.max_mp
                self.assertEqual(robot.native_summon_source["controller_id"], 7)
        self.assertEqual(values[True] - values[False], 2)

    def test_rusty_blade_real_enemy_attack_applies_bonus_and_consumes_marker(self):
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = self.fixture((6485,) if equipped else ())
                self.assertFalse(self.levels(data[2].actors[7], 7918))
                data, far_tx = self.cast(data, 6473, data[2].actors[-7].position)
                self.assertEqual(
                    any(
                        row["kind"] == "state_applied"
                        and row["state_id"] == 7918
                        and row.get("actor_id") == 7
                        for row in far_tx.events
                    ),
                    equipped,
                )
                self.assertEqual(bool(self.levels(data[2].actors[7], 7918)), equipped)
                # Far7916 creates the marker at1025. Near7917 installs357461's
                # original hostile consumer; a subsequent real attack uses it.
                owner = data[2].actors[7].position
                data, _ = self.cast(
                    data, 6473, (owner[0], owner[1] + 1, owner[2]), action_id=11
                )
                # Keep the hostile follow-up in near stance7917. Pay one
                # ordinary MP; do not replace actor position or PA authority.
                data[2].move(
                    data[0]["account_id"], 7, [(owner[0] + 1, owner[1], owner[2])]
                )
                data, followup_tx = self.cast(
                    data, 6473, data[2].actors[-7].position, action_id=12
                )
                self.assertFalse(self.levels(data[2].actors[7], 7918))
                # State8054 belongs to the struck enemy, not the Rogue caster.
                enemy = data[2].actors[-7]
                self.assertEqual(self.levels(enemy, 8054), [25] if equipped else [])
                bonus_receipts = [
                    row
                    for row in followup_tx.events
                    if row.get("kind") == "state_applied"
                    and row.get("state_id") == 8054
                    and row.get("actor_id") == -7
                ]
                self.assertEqual(
                    [row["level"] for row in bonus_receipts], [25] if equipped else []
                )

    def test_master_rogue_actual_turn_start_produces_its_owned_marker(self):
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = self.fixture((7091,) if equipped else ())
                self.assertEqual(
                    self.levels(data[2].actors[7], 8051), [1] if equipped else []
                )
                self.assertFalse(self.levels(data[2].actors[-7], 8051))

    def test_reinforced_tunic_owner_end_with_adjacent_bomb_applies_original_three_states(
        self,
    ):
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = self.fixture((6483,) if equipped else ())
                owner = data[2].actors[7].position
                data, _ = self.cast(data, 7906, (owner[0] + 1, owner[1], owner[2]))
                bomb = self.summons(data[2], (3795, 3796, 3797))[0]
                self.assertEqual(
                    sum(
                        abs(bomb.position[i] - data[2].actors[7].position[i])
                        for i in (0, 1)
                    ),
                    1,
                )
                before = len(data[2].events)
                turns.AniripsaGrantSummonPipelineTests().end_current_turn(data[2], data)
                applied = {
                    (row["actor_id"], row["state_id"])
                    for row in data[2].events[before:]
                    if row["kind"] == "state_applied"
                }
                expected = {(7, 8027), (bomb.id, 8026), (7, 8025)}
                self.assertEqual(applied & expected, expected if equipped else set())
