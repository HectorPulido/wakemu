"""UID routing returns current owner keys without caching carrier objects."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor
from wakfu_server.combat_state_ledger import StateLedger, RunningState
from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_state_membership import (
    attach_actor,
    attach_area,
    attach_detached,
    detach_detached,
    membership_bindings,
    membership_live,
)


def state(uid, target):
    return RunningState(uid, 1, 1, 7, target, -1, "target", False, (), 0, True, None)


class StateMembershipBindingTests(unittest.TestCase):
    def actor(self, identity):
        return Actor(identity, 1, (0, 0, 0), 10, 6, 3, 1, 1)

    def test_duplicate_actor_area_detached_membership_updates_without_global_scan(self):
        owner = RetainedCollections()
        actor = self.actor(-1)
        owner.actors[-1] = actor
        attach_actor(owner, -1, actor)
        actor.state_ledger._entries = (state(91, -1), state(91, -1))
        row = OwnedAreaRow(uid=80, state_ledger=StateLedger(80))
        owner.area_sources["native_effect_areas"][80] = row
        attach_area(owner, 80, row, role="native_effect_areas")
        row["state_ledger"]._entries = (state(91, 80),)
        detached = self.actor(-2)
        owner.detached_actors[-2] = detached
        attach_detached(owner, detached)
        detached.state_ledger._entries = (state(91, -2),)
        with patch.object(
            StateLedger,
            "entries",
            property(
                lambda self: (_ for _ in ()).throw(AssertionError("Global ledger read"))
            ),
        ):
            self.assertEqual(
                set(membership_bindings(owner, 91)),
                {-1, ("area", "native_effect_areas", 80), ("detached", -2)},
            )
            self.assertEqual(membership_bindings(owner, 99), ())
        actor.state_ledger._entries = (state(91, -1),)
        self.assertIn(-1, membership_bindings(owner, 91))
        actor.state_ledger._entries = ()
        detach_detached(owner, detached)
        owner.detached_actors.pop(-2)
        self.assertEqual(
            membership_bindings(owner, 91), (("area", "native_effect_areas", 80),)
        )
        row["state_ledger"]._entries = ()
        self.assertEqual(membership_bindings(owner, 91), ())
        self.assertEqual(set(membership_live(owner)), set())

    def test_replaced_ledger_alias_does_not_reappear_and_selected_carrier_is_fresh(
        self,
    ):
        owner = RetainedCollections()
        actor = self.actor(-1)
        owner.actors[-1] = actor
        attach_actor(owner, -1, actor)
        old = actor.state_ledger
        old._entries = (state(91, -1),)
        new = StateLedger(-1)
        new._entries = (state(92, -1),)
        actor.state_ledger = new
        old._entries = (state(93, -1),)
        self.assertEqual(membership_bindings(owner, 91), ())
        self.assertEqual(membership_bindings(owner, 93), ())
        self.assertEqual(membership_bindings(owner, 92), (-1,))
        previous = new.entries[0]
        updated = replace(previous, level=3)
        new._entries = (updated,)
        self.assertEqual(membership_bindings(owner, 92), (-1,))
        self.assertIs(actor.state_ledger.entries[0], updated)
        new._entries = object()
        self.assertIsNone(membership_bindings(owner, 92))


if __name__ == "__main__":
    unittest.main()
