"""Actual Ardid and turn-start movement branches of Rogue passives."""
import os
import unittest

import test_rogue_runtime_pipeline as pipeline
import test_aniripsa_grant_summon_pipeline as turns


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RogueMobilityPassiveTests(unittest.TestCase):
    fixture = pipeline.RogueRuntimePipelineTests.fixture
    cast = pipeline.RogueRuntimePipelineTests.cast
    los = staticmethod(pipeline.RogueRuntimePipelineTests.los)
    summons = staticmethod(pipeline.RogueRuntimePipelineTests.summons)

    def test_great_escape_self_ardid_swaps_with_an_actual_owned_bomb(self):
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = self.fixture((6480,) if equipped else ())
                data, _ = self.cast(data, 7906)
                bomb = self.summons(data[2], (3795, 3796, 3797))[0]
                owner_position, bomb_position = (
                    data[2].actors[7].position,
                    bomb.position,
                )
                data, _ = self.cast(data, 7904, owner_position, action_id=11)
                self.assertEqual(
                    data[2].actors[7].position,
                    bomb_position if equipped else owner_position,
                )
                if equipped:
                    self.assertEqual(data[2].actors[bomb.id].position, owner_position)

    def test_minesweeper_suppresses_original_off_deck_ardid_state(self):
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = self.fixture((6484,) if equipped else ())
                data, _ = self.cast(data, 7906)
                bomb = self.summons(data[2], (3795, 3796, 3797))[0]
                sequence = data[2].sequence
                data, _ = self.cast(data, 7904, bomb.position, action_id=11)
                applied = [
                    row
                    for row in data[2].events
                    if row["kind"] == "state_applied"
                    and row["sequence"] > sequence
                    and row["state_id"] == 8057
                ]
                if equipped:
                    self.assertEqual(applied, [])
                else:
                    self.assertTrue(applied)
                    self.assertTrue(all(row["level"] == 3 for row in applied))

    def test_fugitive_actual_next_owner_turn_swaps_with_its_supported_bomb(self):
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data = self.fixture((6488,) if equipped else ())
                data, _ = self.cast(data, 7906)
                bomb = self.summons(data[2], (3795, 3796, 3797))[0]
                owner_position, bomb_position = (
                    data[2].actors[7].position,
                    bomb.position,
                )
                helper = turns.AniripsaGrantSummonPipelineTests()
                helper.next_player_turn(data[2], data)
                self.assertEqual(
                    data[2].actors[7].position,
                    bomb_position if equipped else owner_position,
                )
                if equipped:
                    self.assertEqual(data[2].actors[bomb.id].position, owner_position)
