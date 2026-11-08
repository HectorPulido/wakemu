"""Membership reset and opaque-transition journal ordering."""
import unittest

from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_state import Actor
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_state_membership import (
    attach_actor,
    membership_live,
    reset_membership,
)


class MembershipInvalidationTests(unittest.TestCase):
    def test_reset_initializes_empty_membership_without_notifying(self):
        owner = RetainedCollections()
        owner._notify_live_before = lambda uid: self.fail("Reset invoked journal")
        reset_membership(owner)
        self.assertEqual(set(membership_live(owner)), set())

    def test_opaque_entries_capture_old_membership_before_invalidating(self):
        owner = RetainedCollections()
        actor = Actor(-1, 1, (0, 0, 0), 10, 6, 3, 1, 1)
        owner.actors[-1] = actor
        attach_actor(owner, -1, actor)
        actor.state_ledger._entries = (
            RunningState(91, 1, 1, -1, -1, -1, "target", False, (), 0, True, None),
        )
        observed = []
        frozen = []
        owner._invalidate_live_scopes = lambda: frozen.append(
            set(membership_live(owner))
        )
        owner._notify_live_before = lambda uid: observed.append(
            (uid, set(membership_live(owner)))
        )
        actor.state_ledger._entries = object()
        self.assertEqual(observed, [(91, {91})])
        self.assertEqual(frozen, [{91}])
        self.assertIsNone(membership_live(owner))


if __name__ == "__main__":
    unittest.main()
