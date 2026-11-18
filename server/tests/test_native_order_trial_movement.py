"""Source-bound 328 movement authority for the registered pizzlarva."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_combat_summon_retirement as summon_fixture
from wakfu_server import (
    combat_automatic_npc_turn,
    combat_effect_dispatch,
    combat_native_order_hooks,
    combat_state_ledger,
    native_order_trial_movement as movement,
)


class NativeOrderTrialMovementTests(unittest.TestCase):
    def fixture(self):
        fight, owner, _enemy, larva = summon_fixture.SummonRetirementTests().fight(
            origin="ordinary"
        )
        # The source family's actual pizzlarva prototype is3206; 307 names the
        # native summon relation source, not the actor's species reference.
        larva.native_summon_source["ref"] = 3206
        fight.native_summon_registrations[larva.id]["authority"]["breed_id"] = 3206
        larva.controlled = False
        larva.owner_id = None
        larva.native_controlled_by_ai = False
        fight.phase = "active"
        fight.order = [owner.id, larva.id, -7]
        fight.turn_index = 1
        fight.turn_id = 3
        fight.native_order_trial = {"fixture": "validated by order checkpoint"}
        fight.native_order_movement_policy = dict(movement.POLICY)
        fight.edges = {
            (start, end)
            for start in fight.walkable
            for end in fight.walkable
            if abs(start[0] - end[0]) + abs(start[1] - end[1]) == 1
        }
        parent = combat_state_ledger.RunningState(
            9100,
            3127,
            1,
            owner.id,
            larva.id,
            5,
            "caster",
            False,
            (120675,),
            0,
            True,
            None,
        )
        larva.state_ledger._entries = (parent,)
        proof = SimpleNamespace(
            owner_id=owner.id, account_id=owner.owner_id, mode="hard"
        )
        fight.native_order_lane = dict(
            schema="reviewed-native-order-lane-v1",
            mode="hard",
            geometry_sha256="a" * 64,
            authority="test-pinned-lane",
            track=[[1, 1, 0], [2, 1, 0], [2, 2, 0], [1, 2, 0]],
        )
        return fight, owner, larva, parent, proof

    def validated(self, proof):
        return (proof, object(), object())

    def test_eligible_registered_307_larva_with_3127_can_take_automatic_turn(self):
        fight, _owner, larva, _parent, proof = self.fixture()
        with patch(
            "wakfu_server.native_order_trial_checkpoint.validate",
            return_value=self.validated(proof),
        ):
            self.assertTrue(movement.eligible(fight, larva))
            self.assertTrue(
                combat_automatic_npc_turn.requires_automatic_npc_turn_end(fight, larva)
            )

        unattested = deepcopy(fight)
        unattested.native_order_movement_policy = None
        with patch(
            "wakfu_server.native_order_trial_checkpoint.validate",
            return_value=self.validated(proof),
        ):
            self.assertFalse(
                combat_automatic_npc_turn.requires_automatic_npc_turn_end(
                    unattested, unattested.actors[larva.id]
                )
            )

        off_turn = deepcopy(fight)
        off_turn.turn_index = 0
        with patch(
            "wakfu_server.native_order_trial_checkpoint.validate",
            return_value=self.validated(proof),
        ):
            self.assertFalse(movement.eligible(off_turn, off_turn.actors[larva.id]))

    def test_native_328_command_binds_cell_carrier_runner_and_turn(self):
        fight, _owner, larva, parent, proof = self.fixture()
        handler = combat_native_order_hooks.NativeOrderHookHandler(
            fight,
            [],
            action_id=9,
            allocate_uid=lambda: 8001,
            context=None,
            retention=None,
            rng=None,
            actor_authority=None,
        )
        invocation = combat_effect_dispatch.EffectInvocation(
            reference=120675,
            level=1,
            caster_id=larva.id,
            target_id=larva.id,
            cell=larva.position,
            state_uid=parent.uid,
        )
        cell = combat_native_order_hooks.NativeOrderCell(2, 1, 0)
        with patch(
            "wakfu_server.native_order_trial_checkpoint.validate",
            return_value=self.validated(proof),
        ):
            command = movement.record(
                handler,
                {"effect_class": 328},
                invocation,
                runner_uid=8002,
                cell=cell,
                value=3,
            )
            self.assertEqual(command["anchor"], [2, 1, 0])
            self.assertEqual(command["carrier_uid"], parent.uid)
            self.assertEqual(command["runner_uid"], 8002)
            with patch(
                "wakfu_server.combat_tackle_movement.movement_tackle_cost",
                return_value=(0, 0),
            ):
                self.assertEqual(
                    movement.path_for(fight, larva, command),
                    ((2, 1, 0), (2, 2, 0), (1, 2, 0)),
                )

            stale = dict(command, turn_id=fight.turn_id - 1)
            with self.assertRaisesRegex(ValueError, "Stale or foreign"):
                movement.path_for(fight, larva, stale)
            expired = deepcopy(fight)
            expired_actor = expired.actors[larva.id]
            expired_actor.state_ledger._entries = ()
            with self.assertRaisesRegex(
                ValueError, "native turn authority|carrier expired"
            ):
                movement.path_for(expired, expired_actor, command)

            with self.assertRaisesRegex(ValueError, "actual native328"):
                movement.record(
                    handler,
                    {"effect_class": 327},
                    invocation,
                    runner_uid=8003,
                    cell=cell,
                    value=3,
                )
            with self.assertRaisesRegex(ValueError, "outside the actual arcade"):
                movement.record(
                    handler,
                    {"effect_class": 328},
                    invocation,
                    runner_uid=8004,
                    cell=combat_native_order_hooks.NativeOrderCell(9, 9, 0),
                    value=3,
                )

        malformed = deepcopy(fight)
        malformed.native_order_movement_policy["operand"] = 4
        with patch(
            "wakfu_server.native_order_trial_checkpoint.validate",
            return_value=self.validated(proof),
        ):
            with self.assertRaisesRegex(ValueError, "frozen server policy"):
                movement.eligible(malformed, malformed.actors[larva.id])

        malformed_lane = deepcopy(fight)
        malformed_lane.native_order_lane["mode"] = "normal"
        with patch(
            "wakfu_server.native_order_trial_checkpoint.validate",
            return_value=self.validated(proof),
        ):
            with self.assertRaisesRegex(ValueError, "pinned reviewed lane"):
                movement.path_for(
                    malformed_lane, malformed_lane.actors[larva.id], command
                )

        broken_path = deepcopy(fight)
        broken_path.native_order_lane["track"] = [[1, 1, 0], [3, 3, 0]]
        with patch(
            "wakfu_server.native_order_trial_checkpoint.validate",
            return_value=self.validated(proof),
        ):
            with self.assertRaisesRegex(ValueError, "directed native floor path"):
                movement.path_for(broken_path, broken_path.actors[larva.id], command)

    def test_registered_order_path_spends_real_movement_points(self):
        fight, _owner, larva, parent, proof = self.fixture()
        handler = combat_native_order_hooks.NativeOrderHookHandler(
            fight,
            [],
            action_id=9,
            allocate_uid=lambda: 8001,
            context=None,
            retention=None,
            rng=None,
            actor_authority=None,
        )
        invocation = combat_effect_dispatch.EffectInvocation(
            reference=120675,
            level=1,
            caster_id=larva.id,
            target_id=larva.id,
            cell=larva.position,
            state_uid=parent.uid,
        )
        with patch(
            "wakfu_server.native_order_trial_checkpoint.validate",
            return_value=self.validated(proof),
        ):
            command = movement.record(
                handler,
                {"effect_class": 328},
                invocation,
                runner_uid=8002,
                cell=combat_native_order_hooks.NativeOrderCell(2, 1, 0),
                value=3,
            )
            same_anchor = deepcopy(fight)
            same_actor = same_anchor.actors[larva.id]
            same_command = same_anchor.native_order_commands[str(same_actor.id)]
            same_command["anchor"] = list(same_actor.position)
            with patch(
                "wakfu_server.combat_tackle_movement.movement_tackle_cost",
                return_value=(0, 0),
            ):
                self.assertEqual(
                    movement.path_for(same_anchor, same_actor, same_command),
                    ((2, 1, 0), (2, 2, 0), (1, 2, 0)),
                )
            with patch(
                "wakfu_server.combat_tackle_movement.movement_tackle_cost",
                return_value=(0, 0),
            ):
                path = movement.path_for(fight, larva, command)
                before_mp, before = larva.mp, larva.position
                event = fight._move_actor(larva, path)
        self.assertEqual(event["path"], ((2, 1, 0), (2, 2, 0), (1, 2, 0)))
        self.assertEqual(larva.position, (1, 2, 0))
        self.assertEqual(larva.mp, before_mp - 3)
        self.assertEqual(before, (1, 1, 0))

        self.assertEqual(command["anchor"], [2, 1, 0])
        self.assertNotEqual(
            command["anchor"], list(fight.native_order_lane["track"][-1])
        )

    def test_operand_three_uses_lane_and_actual_mp_not_distance_or_facing(self):
        for mp, expected in (
            (0, ()),
            (1, ((2, 1, 0),)),
            (2, ((2, 1, 0), (2, 2, 0))),
        ):
            fight, _owner, larva, parent, proof = self.fixture()
            larva.mp = mp
            handler = combat_native_order_hooks.NativeOrderHookHandler(
                fight,
                [],
                action_id=9,
                allocate_uid=lambda: 8001,
                context=None,
                retention=None,
                rng=None,
                actor_authority=None,
            )
            invocation = combat_effect_dispatch.EffectInvocation(
                reference=120675,
                level=1,
                caster_id=larva.id,
                target_id=larva.id,
                cell=larva.position,
                state_uid=parent.uid,
            )
            with patch(
                "wakfu_server.native_order_trial_checkpoint.validate",
                return_value=self.validated(proof),
            ):
                command = movement.record(
                    handler,
                    {"effect_class": 328},
                    invocation,
                    runner_uid=8002,
                    cell=combat_native_order_hooks.NativeOrderCell(2, 1, 0),
                    value=3,
                )
                larva.direction = 0
                with patch(
                    "wakfu_server.combat_tackle_movement.movement_tackle_cost",
                    return_value=(0, 0),
                ):
                    forward_a = movement.path_for(fight, larva, command)
                larva.direction = 7
                with patch(
                    "wakfu_server.combat_tackle_movement.movement_tackle_cost",
                    return_value=(0, 0),
                ):
                    forward_b = movement.path_for(fight, larva, command)
                self.assertEqual(forward_a, expected)
                self.assertEqual(forward_b, expected)
                self.assertEqual(command["operand"], 3)

                blocked = deepcopy(fight)
                blocked_actor = blocked.actors[larva.id]
                blocked_command = blocked.native_order_commands[str(larva.id)]
                blocked_actor.mp = 2
                with patch(
                    "wakfu_server.combat_qi_movement.movement_blocked_cells",
                    return_value={(2, 1, 0)},
                ):
                    with patch(
                        "wakfu_server.combat_tackle_movement.movement_tackle_cost",
                        return_value=(0, 0),
                    ):
                        self.assertEqual(
                            movement.path_for(blocked, blocked_actor, blocked_command),
                            (),
                        )

    def test_consumed_and_prior_turn_commands_are_idempotent_but_still_validated(self):
        fight, _owner, larva, parent, proof = self.fixture()
        handler = combat_native_order_hooks.NativeOrderHookHandler(
            fight,
            [],
            action_id=9,
            allocate_uid=lambda: 8001,
            context=None,
            retention=None,
            rng=None,
            actor_authority=None,
        )
        invocation = combat_effect_dispatch.EffectInvocation(
            reference=120675,
            level=1,
            caster_id=larva.id,
            target_id=larva.id,
            cell=larva.position,
            state_uid=parent.uid,
        )
        with patch(
            "wakfu_server.native_order_trial_checkpoint.validate",
            return_value=self.validated(proof),
        ):
            recorded = movement.record(
                handler,
                {"effect_class": 328},
                invocation,
                runner_uid=8002,
                cell=combat_native_order_hooks.NativeOrderCell(2, 1, 0),
                value=3,
            )

        for command in (
            dict(recorded, consumed=True),
            dict(recorded, consumed=True, turn_id=fight.turn_id - 1),
            dict(recorded, consumed=False, turn_id=fight.turn_id - 1),
        ):
            current = deepcopy(fight)
            selected = current.actors[larva.id]
            current.native_order_commands[str(larva.id)] = command
            before = (
                selected.position,
                selected.mp,
                deepcopy(current.events),
                deepcopy(command),
            )
            with patch(
                "wakfu_server.native_order_trial_checkpoint.validate",
                return_value=self.validated(proof),
            ):
                self.assertEqual(
                    movement.move_current(SimpleNamespace(fight=current)), []
                )
            self.assertEqual(
                (
                    selected.position,
                    selected.mp,
                    current.events,
                    current.native_order_commands[str(larva.id)],
                ),
                before,
            )

        invalid_commands = (
            dict(recorded, consumed=True, actor_id=777777),
            dict(recorded, consumed=True, effect_reference=1),
            dict(recorded, consumed=True, runner_uid="bad"),
            dict(recorded, consumed=True, turn_id=fight.turn_id + 1),
        )
        for command in invalid_commands:
            with self.subTest(command=command):
                current = deepcopy(fight)
                selected = current.actors[larva.id]
                current.native_order_commands[str(larva.id)] = command
                before = (selected.position, selected.mp, deepcopy(current.events))
                with patch(
                    "wakfu_server.native_order_trial_checkpoint.validate",
                    return_value=self.validated(proof),
                ):
                    with self.assertRaises(ValueError):
                        movement.move_current(SimpleNamespace(fight=current))
                self.assertEqual(
                    (selected.position, selected.mp, current.events), before
                )

        expired = deepcopy(fight)
        selected = expired.actors[larva.id]
        selected.state_ledger._entries = (
            combat_state_ledger.RunningState(
                9101,
                3127,
                1,
                _owner.id,
                larva.id,
                5,
                "caster",
                False,
                (120675,),
                0,
                True,
                None,
            ),
        )
        expired.native_order_commands[str(larva.id)] = dict(recorded, consumed=True)
        with patch(
            "wakfu_server.native_order_trial_checkpoint.validate",
            return_value=self.validated(proof),
        ):
            with self.assertRaisesRegex(ValueError, "carrier expired"):
                movement.move_current(SimpleNamespace(fight=expired))


if __name__ == "__main__":
    unittest.main()
