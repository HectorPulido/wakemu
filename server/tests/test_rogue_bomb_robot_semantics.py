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
                    (caster.position[0] - 1, caster.position[1], caster.position[2])
                    if reference == 7952
                    else (
                        caster.position[0],
                        caster.position[1] - 1,
                        caster.position[2],
                    ),
                    action_id=11,
                )
                robot = self.summons(data[2], (1236,))[0]
                if reference == 7952:
                    # Pending native cast-facing metadata must not invent a
                    # rotation. Vacate the owner cell using ordinary paid MP.
                    data[2].move(
                        data[0]["account_id"], 7, [(owner[0], owner[1] - 1, owner[2])]
                    )
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
                if reference == 7952:
                    # Native anE contains one oriented adjacent point. Keep the
                    # owned bomb adjacent, then aim at the free cell beyond it.
                    path = [(owner[0], owner[1], owner[2])]
                from wakfu_server.combat_runtime_messages import RuntimeMessages
                from wakfu_server.combat_movement_runtime import apply_client
                import struct

                apply_client(
                    RuntimeMessages(data[2]),
                    data[0]["account_id"],
                    struct.pack(">q", robot.id)
                    + b"".join(struct.pack(">iih", *cell) for cell in path),
                    lambda actor: b"owned-test-stats",
                )
                if reference == 7952:
                    self.assertIn(
                        (bomb.position[0] + 1, bomb.position[1], bomb.position[2]),
                        data[2].walkable,
                    )
                before = snapshot(data[2])
                before_bomb_position = tuple(data[2].actors[bomb.id].position)
                before_robot_position = tuple(data[2].actors[robot.id].position)
                before_bomb_hp = data[2].actors[bomb.id].hp
                before_bomb_max_hp = data[2].actors[bomb.id].max_hp
                before_robot_ap = data[2].actors[robot.id].ap
                before_robot_mp = data[2].actors[robot.id].mp
                before_owner = (
                    data[2].actors[7].hp,
                    data[2].actors[7].ap,
                    data[2].actors[7].mp,
                    data[2].actors[7].position,
                )
                # A foreign account cannot spend this controlled actor's book.
                import struct
                from wakfu_server.combat_server_spell import prepare_server_spell
                from wakfu_server.combat_summon_spellbook import actor_action_book

                row = next(
                    row
                    for row in actor_action_book(data[2].actors[robot.id])["actions"]
                    if row["reference"] == reference
                )
                denied_target = bomb.position if reference != 7952 else robot.position
                rng_before = data[4].getstate()
                with self.assertRaises(ValueError):
                    prepare_server_spell(
                        struct.pack(">qqiih", robot.id, row["uid"], *denied_target),
                        data[0],
                        {-7: data[1]},
                        data[2],
                        4,
                        data[3],
                        action_id=20,
                        critical=None,
                        rng=data[4],
                        line_of_sight=lambda origin, target, preview: self.los(
                            data[0], origin, target, preview
                        ),
                    )
                self.assertEqual(snapshot(data[2]), before)
                self.assertEqual(data[4].getstate(), rng_before)
                from wakfu_server.combat_diagnostics import combat_diagnostic_scope

                trace = []
                with combat_diagnostic_scope(lambda **event: trace.append(event)):
                    data, tx = self.cast(
                        data,
                        reference,
                        (bomb.position[0] + 1, bomb.position[1], bomb.position[2])
                        if reference == 7952
                        else bomb.position,
                        actor_id=robot.id,
                        action_id=21,
                    )
                if reference == 6520:
                    import json
                    from pathlib import Path

                    Path(
                        ".runtime/rogue-qualification-20261011/robot-strengthened/6520-receipts-diagnostic.json"
                    ).write_text(
                        json.dumps(
                            {
                                "events": tx.events,
                                "trace": trace,
                                "bomb_states": list(
                                    data[2].actors[bomb.id].state_ledger.entries
                                ),
                            },
                            default=str,
                            indent=2,
                        )
                    )
                self.assertNotEqual(snapshot(data[2]), before)
                self.assertTrue(any(tx.outcomes))
                # Actual native casting/resource metadata for all three actions
                # gives 1AP and no movement cost, on the controlled robot.
                self.assertEqual(data[2].actors[robot.id].ap, before_robot_ap - 1)
                self.assertEqual(data[2].actors[robot.id].mp, before_robot_mp)
                self.assertEqual(
                    (
                        data[2].actors[7].hp,
                        data[2].actors[7].ap,
                        data[2].actors[7].mp,
                        data[2].actors[7].position,
                    ),
                    before_owner,
                )
                expected_root = {6520: 371647, 7951: 358998, 7952: 359001}[reference]
                self.assertTrue(
                    any(
                        row.get("effect_reference") == expected_root
                        and row.get("status") == "completed"
                        for row in trace
                    ),
                    trace,
                )
                if reference == 6520:
                    receipts = [
                        row
                        for row in tx.events
                        if row.get("kind") == "state_applied"
                        and row.get("state_id") == 8057
                    ]
                    self.assertEqual(
                        [(row["actor_id"], row["level"]) for row in receipts],
                        [(bomb.id, 2)],
                    )
                    self.assertEqual(
                        data[2].actors[bomb.id].position, before_bomb_position
                    )
                elif reference == 7951:
                    # Native family301 pulls the selected bomb toward the robot;
                    # this legal fixture starts two cells away on the same column.
                    self.assertEqual(
                        abs(before_bomb_position[1] - before_robot_position[1]), 2
                    )
                    self.assertEqual(
                        data[2].actors[bomb.id].position,
                        (
                            before_bomb_position[0],
                            before_bomb_position[1] - 1,
                            before_bomb_position[2],
                        ),
                    )
                else:
                    # Cast CELL is two away; anE's adjacent oriented point
                    # contains the bomb, so native781 branch uses PUSH1.
                    self.assertEqual(data[2].actors[robot.id].direction, 1)
                    self.assertEqual(
                        before_bomb_position,
                        (
                            before_robot_position[0] + 1,
                            before_robot_position[1],
                            before_robot_position[2],
                        ),
                    )
                    self.assertEqual(
                        data[2].actors[bomb.id].position,
                        (
                            before_bomb_position[0] + 1,
                            before_bomb_position[1],
                            before_bomb_position[2],
                        ),
                    )
                    self.assertTrue(
                        any(
                            row.get("effect_reference") == 359006
                            and row.get("status") == "completed"
                            for row in trace
                        ),
                        trace,
                    )
                    self.assertFalse(
                        any(
                            row.get("reference") == 781
                            for row in data[2].native_effect_areas.values()
                        )
                    )
                if reference == 6520:
                    # Native8057 emits2210;372460/372461 consume its two
                    # levels into bomb7923 L1->L3 and rebuild authored HP.
                    states = {
                        row.reference: row.level
                        for row in data[2].actors[bomb.id].state_ledger.entries
                    }
                    self.assertEqual(states[7923], 3)
                    self.assertEqual(states[7935], 3)
                    self.assertNotIn(8057, states)
                    self.assertTrue(
                        any(
                            row.get("kind") == "state_removed"
                            and row.get("reference") == 8057
                            and row.get("actor_id") == bomb.id
                            for row in tx.events
                        )
                    )
                    self.assertEqual(data[2].actors[bomb.id].hp, before_bomb_hp * 3)
                    self.assertEqual(
                        data[2].actors[bomb.id].max_hp, before_bomb_max_hp * 3
                    )
                else:
                    self.assertEqual(data[2].actors[bomb.id].hp, before_bomb_hp)
                self.assertEqual(
                    data[2].actors[robot.id].position, before_robot_position
                )
                self.assertEqual(
                    data[2].actors[robot.id].native_summon_source["controller_id"], 7
                )
