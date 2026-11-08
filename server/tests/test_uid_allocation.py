"""Focused collision proofs for the isolated allocator gateway."""
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.combat_state_membership import (
    attach_actor,
    membership_actor_live,
    membership_live,
)
from wakfu_server.combat_retained_collections import bound_collections
from wakfu_server.combat_area_membership import OwnedAreaRow


def make_fight():
    first = Actor(1, 0, (0, 0, 0), 10, 6, 3, 20, 1)
    second = Actor(2, 1, (1, 0, 0), 10, 6, 3, 10, 1)
    fight = Fight(
        1,
        [first, second],
        {first.position, second.position},
        {0: {first.position}, 1: {second.position}},
    )
    owner = bound_collections(vars(fight))
    for key, actor in fight.actors.items():
        attach_actor(owner, key, actor)
    return fight


def state(uid):
    return RunningState(uid, 1, 1, -1, -1, 1, "target", False, (), 0, True, None)


class UIDAllocationGatewayTests(unittest.TestCase):
    def test_ledger_only_collision_is_rejected_without_advancing(self):
        fight = make_fight()
        fight.native_effect_uid_next = 101
        actor = fight.actors[1]
        actor.state_ledger._entries = (state(101),)
        with self.assertRaisesRegex(ValueError, "collides with an owned effect"):
            fight.allocate_effect_uid()
        self.assertEqual(fight.native_effect_uid_next, 101)

    def test_source_map_collision_is_rejected_without_advancing(self):
        fight = make_fight()
        fight.native_effect_uid_next = 202
        fight.native_owned_group_effects[202] = {"uid": 202}
        with self.assertRaisesRegex(ValueError, "collides with an owned effect"):
            fight.allocate_effect_uid()
        self.assertEqual(fight.native_effect_uid_next, 202)

    def test_area_uid_skips_owned_area_pv_collision(self):
        fight = make_fight()
        fight.native_effect_uid_next = 303
        fight.native_owned_area_effects[7] = {"uid": 7, "area_uid": 303}
        self.assertEqual(fight.allocate_area_uid(), 304)
        self.assertEqual(fight.native_effect_uid_next, 305)

    def test_area_ledger_uid_is_not_an_actor_effect_uid_collision(self):
        fight = make_fight()
        owner = bound_collections(vars(fight))
        area_ledger = StateLedger(80)
        area_ledger._entries = (state(404),)
        fight.native_effect_areas[80] = OwnedAreaRow(
            uid=80,
            state_ledger=area_ledger,
        )
        self.assertIn(404, membership_live(owner))
        self.assertNotIn(404, membership_actor_live(owner))
        fight.native_effect_uid_next = 404
        self.assertEqual(fight.allocate_effect_uid(), 404)

    def test_actor_ledger_uid_remains_an_effect_uid_collision(self):
        fight = make_fight()
        fight.native_effect_uid_next = 505
        fight.actors[1].state_ledger._entries = (state(505),)
        with self.assertRaisesRegex(ValueError, "collides with an owned effect"):
            fight.allocate_effect_uid()
        self.assertEqual(fight.native_effect_uid_next, 505)

    def test_unhashable_ledger_uid_preserves_original_fallback_error_order(self):
        fight = make_fight()
        fight.native_effect_uid_next = 606
        fight.state_wire_payloads[606] = "00"
        malformed = state([])
        fight.actors[1].state_ledger._entries = (malformed,)
        with self.assertRaises(TypeError):
            fight.allocate_effect_uid()
        self.assertEqual(fight.native_effect_uid_next, 606)

    def test_actor_accessor_override_disables_stale_membership_fastpath(self):
        fight = make_fight()
        actor = fight.actors[1]
        actor.state_ledger._entries = (state(707),)
        empty_ledger = StateLedger(actor.id)
        original_getattribute = Actor.__getattribute__

        def overridden_getattribute(instance, name):
            if instance is actor and name == "state_ledger":
                return empty_ledger
            return original_getattribute(instance, name)

        fight.native_effect_uid_next = 707
        Actor.__getattribute__ = overridden_getattribute
        try:
            self.assertEqual(fight.allocate_effect_uid(), 707)
        finally:
            Actor.__getattribute__ = original_getattribute


if __name__ == "__main__":
    unittest.main()
