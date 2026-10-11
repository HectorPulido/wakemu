"""Actual Rogue bomb element constructors and controlled robot actions."""
import os
import unittest
from unittest.mock import patch
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_summon_handler import NativeSummonHandler

import test_rogue_runtime_pipeline as pipeline
import test_rogue_elemental_semantics as elemental
import test_aniripsa_grant_summon_pipeline as turns
from wakfu_server.fight_checkpoint_store import snapshot


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RogueBombRobotSemanticsTests(unittest.TestCase):
    cast = pipeline.RogueRuntimePipelineTests.cast
    los = staticmethod(pipeline.RogueRuntimePipelineTests.los)
    summons = staticmethod(pipeline.RogueRuntimePipelineTests.summons)

    def test_three_elemental_free_cell_branches_create_original_bomb_profiles(self):
        helper = pipeline.RogueRuntimePipelineTests()
        observed = set()
        for reference, profile in ((6465, 3796), (6468, 3797), (6473, 3795)):
            with self.subTest(reference=reference):
                data = elemental.RogueElementalSemanticsTests().fixture(reference)
                owner = data[2].actors[7].position
                cell = (owner[0] + 1, owner[1], owner[2])
                enemy_before = data[2].actors[-7].position
                births = []
                original = NativeSummonHandler.__call__

                def observe(handler, effect, values, invocation):
                    before = set(handler.fight.actors)
                    result = original(handler, effect, values, invocation)
                    for identity in set(handler.fight.actors) - before:
                        actor = handler.fight.actors[identity]
                        births.append(
                            (
                                identity,
                                actor.position,
                                actor.native_summon_source["ref"],
                                actor.native_summon_source["controller_id"],
                                any(
                                    row and row["identity"] == ["actor", identity]
                                    for row in handler.fight.native_qi_slots
                                ),
                            )
                        )
                    return result

                with patch.object(NativeSummonHandler, "__call__", observe):
                    data, _ = helper.cast(data, reference, cell)
                bomb = helper.summons(data[2], (3795, 3796, 3797))[0]
                self.assertEqual(births, [(bomb.id, cell, profile, 7, True)])
                self.assertEqual(bomb.native_summon_source["controller_id"], 7)
                observed.add(profile)
                self.assertNotIn(bomb.id, data[2].order)
                self.assertGreater(bomb.native_fight_property_counts[114], 0)
                if reference == 6468:
                    swaps = [
                        row
                        for row in data[2].events
                        if row["kind"] == "effect_displacement"
                        and row["effect_class"] == 422
                        and row["caster_id"] == bomb.id
                    ]
                    self.assertEqual(len(swaps), 1)
                    self.assertEqual(
                        dict(swaps[0]["actors"]), {bomb.id: enemy_before, -7: cell}
                    )
                    self.assertEqual(bomb.position, enemy_before)
                    self.assertEqual(data[2].actors[-7].position, cell)
                else:
                    self.assertEqual(bomb.position, cell)
        self.assertEqual(observed, {3795, 3796, 3797})

    def test_other_three_robot_actions_use_actual_controlled_turn_and_owned_bomb(self):
        for reference in (6520, 7951, 7952):
            with self.subTest(reference=reference):
                data = pipeline.RogueRuntimePipelineTests().fixture()
                owner = data[2].actors[7].position
                data, _ = self.cast(data, 7906, (owner[0] + 1, owner[1], owner[2]))
                bomb = self.summons(data[2], (3795, 3796, 3797))[0]
                caster = data[2].actors[7]
                data, _ = self.cast(
                    data,
                    7905,
                    (caster.position[0], caster.position[1] - 1, caster.position[2]),
                    action_id=11,
                )
                robot = self.summons(data[2], (1236,))[0]
                helper = turns.AniripsaGrantSummonPipelineTests()
                for _ in range(20):
                    if data[2].current.id == robot.id:
                        break
                    helper.end_current_turn(data[2], data)
                self.assertEqual(data[2].current.id, robot.id)
                # Creation7905 is adjacent-only. Pay real MP on the robot's
                # controlled turn to obtain a clear two-cell line to the bomb.
                path = [
                    (bomb.position[0], robot.position[1], robot.position[2]),
                    (bomb.position[0], robot.position[1] - 1, robot.position[2]),
                ]
                data[2].move(data[0]["account_id"], robot.id, path)
                before = snapshot(data[2])
                data, tx = self.cast(
                    data,
                    reference,
                    None if reference == 7952 else bomb.position,
                    actor_id=robot.id,
                    action_id=21,
                )
                self.assertNotEqual(snapshot(data[2]), before)
                self.assertTrue(any(tx.outcomes))
                self.assertEqual(
                    data[2].actors[robot.id].native_summon_source["controller_id"], 7
                )
