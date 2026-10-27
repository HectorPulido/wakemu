"""Private PvE cleanup preserves the actual retired QI/PV root authority."""
from copy import deepcopy
import struct
import unittest

import test_combat_pve_departure as departure_fixture
from wakfu_server.combat_abandon import _participant, committed_abandon_team
from wakfu_server.combat_global_pv_collections import global_pv_iterator
from wakfu_server.combat_pve_departure import retired_pve_actor_ids
from wakfu_server.combat_pve_withdraw import plan
from wakfu_server.combat_qi_fight import current_registry
from wakfu_server.combat_results import continuation
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Session
from wakfu_server.fight_checkpoint_store import snapshot


class PrivateDepartureContinuationTests(unittest.TestCase):
    def test_native_two_owner_private_exit_preserves_retirement_and_owner_fences(self):
        fight = departure_fixture.PvEDepartureTests().fixture()
        before = snapshot(fight)
        runtime = RuntimeMessages(fight)
        withdrawal = plan(Session(1, 10, "owner", 527, 0), fight, runtime)
        private = withdrawal.private_runtime
        old_slot = fight.actors[10].native_obstacle_id

        for candidate in (withdrawal.fight, private.fight):
            self.assertTrue(candidate.actors[10].pve_withdrawn)
            self.assertEqual(retired_pve_actor_ids(candidate), {10})
            self.assertIsNone(current_registry(candidate).slots[old_slot])
            self.assertNotIn(
                10,
                tuple(global_pv_iterator(candidate, caster_id=20, caster_only=False)),
            )
        self.assertEqual(_participant(1, {"id": 10}, private).id, 10)
        self.assertEqual(committed_abandon_team(private), 0)
        self.assertTrue(continuation(fight.id, struct.pack(">iB", fight.id, 1)))
        self.assertEqual(
            [opcode for opcode, _body in withdrawal.private_packets], [12238, 13420]
        )
        self.assertNotIn(12238, [opcode for opcode, _body in withdrawal.public_packets])
        self.assertEqual(withdrawal.fight.phase, "active")
        self.assertEqual(withdrawal.fight.actors[20].hp, 55)
        self.assertEqual(withdrawal.fight.actors[-200].hp, 25)
        self.assertEqual(private.fight.phase, "finished")
        self.assertIsNone(private.fight.winner)
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(runtime.action_id, 0)

        for mutate in (
            lambda current: delattr(current, "pve_withdrawal_owner"),
            lambda current: setattr(current, "pve_withdrawal_owner", (2, 20)),
            lambda current: setattr(current, "abandon_owner", (2, 20)),
            lambda current: setattr(current.fight, "phase", "active"),
            lambda current: setattr(current.fight, "winner", 0),
            lambda current: current.fight.native_pve_departures[10].update(
                source="foreign"
            ),
            lambda current: current.fight.native_pve_departures[10].update(
                root_actor_id=20
            ),
            lambda current: current.fight.native_pve_departures.clear(),
        ):
            rejected = deepcopy(private)
            mutate(rejected)
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                with self.assertRaises(ValueError):
                    _participant(1, {"id": 10}, rejected)
                with self.assertRaises(ValueError):
                    committed_abandon_team(rejected)
        with self.assertRaises(ValueError):
            _participant(2, {"id": 10}, private)
        with self.assertRaises(ValueError):
            _participant(2, {"id": 20}, private)
        with self.assertRaises(ValueError):
            continuation(fight.id, struct.pack(">iB", fight.id + 1, 1))


if __name__ == "__main__":
    unittest.main()
