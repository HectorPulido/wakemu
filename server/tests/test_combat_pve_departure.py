"""Actual owned withdrawal retires native populations and retains history."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    global_pv_iterator,
)
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
    current_registry,
)
from wakfu_server.combat_pve_withdraw import plan
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Session
from wakfu_server.combat_casting_context import NativeOwnedCastingContext


class PvEDepartureTests(unittest.TestCase):
    def fixture(self):
        cells = {(x, 0, 0) for x in range(3)}
        fight = Fight(
            77,
            [
                Actor(10, 0, (0, 0, 0), 45, 6, 3, 100, 1, 1, True),
                Actor(20, 0, (1, 0, 0), 55, 6, 3, 90, 1, 2, True),
                Actor(-200, 1, (2, 0, 0), 25, 4, 2, 1, 1),
            ],
            cells,
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0)}},
        )
        for actor in fight.actors.values():
            actor.physical_radius = 0
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=3, height=1, cell_masks=[0, 0, 0]
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(
                fight, physical_radii={identity: 0 for identity in fight.actors}
            ),
        )
        fight.ready(1)
        fight.ready(2)
        return fight

    def test_withdrawal_retires_qi_and_pv_without_death_or_history_loss(self):
        original = self.fixture()
        old_slot = original.actors[10].native_obstacle_id
        result = plan(
            Session(1, 10, "owner", 527, 0), original, RuntimeMessages(original)
        )
        fight = result.fight
        self.assertEqual(fight.actors[10].hp, 0)
        self.assertTrue(fight.actors[10].pve_withdrawn)
        self.assertEqual(fight.actors[10].native_obstacle_id, -1)
        self.assertIsNone(current_registry(fight).slots[old_slot])
        self.assertEqual(current_registry(fight).ordered_U(0, 0), ())
        self.assertFalse(any(event.get("kind") == "death" for event in fight.events))
        self.assertNotIn(
            10, tuple(global_pv_iterator(fight, caster_id=20, caster_only=False))
        )
        self.assertEqual(original.actors[10].hp, 45)
        self.assertIsNotNone(current_registry(original).slots[old_slot])
        adapter = SimpleNamespace(
            _actor=lambda *_args: SimpleNamespace(targeting={"is_eGj": True})
        )
        query = object.__new__(NativeOwnedCastingContext)
        query._registry = None
        query.fight, query.adapter, query.cell = fight, adapter, (0, 0, 0)
        query.resolve_target_fighter()
        self.assertIsNone(query.target)
        query.cell = (2, 0, 0)
        query.resolve_target_fighter()
        self.assertEqual(query.target.id, -200)

    def test_raw_withdrawal_flag_and_stale_slot_do_not_supply_authority(self):
        fight = self.fixture()
        malformed = deepcopy(fight)
        malformed.actors[10].hp = 0
        malformed.actors[10].pve_withdrawn = True
        with self.assertRaises(ValueError):
            current_registry(malformed)
        result = plan(Session(1, 10, "owner", 527, 0), fight, RuntimeMessages(fight))
        slot = fight.actors[10].native_obstacle_id
        result.fight.native_qi_slots[slot] = deepcopy(fight.native_qi_slots[slot])
        with self.assertRaisesRegex(ValueError, "remains registered"):
            current_registry(result.fight)
