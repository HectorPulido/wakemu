"""Actor state membership without catalog, packets, or database services."""
from copy import deepcopy
import gc
import unittest
from weakref import ref

from wakfu_server.combat_state import Actor
from wakfu_server.combat_state_ledger import StateLedger, RunningState
from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_state_membership import (
    attach_actor,
    detach_actor,
    membership_live,
)
from wakfu_server.combat_state_mutation import publish_membership, StateMembershipChange


def state(uid):
    return RunningState(uid, 1, 1, -1, -1, -1, "target", False, (), 0, True, None)


class StateMembershipGatewayTests(unittest.TestCase):
    def setup_owner(self):
        owner = RetainedCollections()
        actor = Actor(-1, 1, (0, 0, 0), 10, 6, 3, 1, 1)
        owner.actors[-1] = actor
        attach_actor(owner, -1, actor)
        return owner, actor

    def test_uid_without_wire_reuse_and_nested_membership_read_current_ledger(self):
        owner, actor = self.setup_owner()
        observed = []
        owner._notify_live_before = lambda uid: observed.append(
            (uid, set(membership_live(owner)))
        )
        actor.state_ledger._entries = (state(91),)
        self.assertEqual(set(membership_live(owner)), {91})
        self.assertEqual(observed[0], (91, set()))
        self.assertEqual(owner.sources["state_wire_payloads"], {})
        # Recursive publication changes membership before outer publication.
        publish_membership(
            actor.state_ledger, StateMembershipChange(frozenset({91}), (state(92),))
        )
        publish_membership(
            actor.state_ledger, StateMembershipChange(frozenset(), (state(91),))
        )
        self.assertEqual(set(membership_live(owner)), {91, 92})
        actor.state_ledger.remove(91)
        self.assertEqual(set(membership_live(owner)), {92})

    def test_replaced_ledger_detaches_old_alias_and_new_ledger_remains_live(self):
        owner, actor = self.setup_owner()
        old = actor.state_ledger
        old._entries = (state(91),)
        new = StateLedger(-1)
        new._entries = (state(92),)
        actor.state_ledger = new
        old._entries = (state(93),)
        self.assertEqual(set(membership_live(owner)), {92})
        new._entries = ()
        self.assertEqual(set(membership_live(owner)), set())

    def test_deepcopy_and_codec_restoration_rebind_without_old_owner(self):
        from wakfu_server.combat_reproduction_state import encode_state, decode_state

        owner, actor = self.setup_owner()
        actor.state_ledger._entries = (state(91),)
        for copied in (deepcopy(actor), decode_state(encode_state(actor))):
            other = RetainedCollections()
            other.actors[-1] = copied
            attach_actor(other, -1, copied)
            copied.state_ledger._entries = (state(92),)
            self.assertEqual(set(membership_live(other)), {92})
            self.assertEqual(set(membership_live(owner)), {91})

    def test_registry_does_not_keep_owner_actor_or_ledger_alive(self):
        owner, actor = self.setup_owner()
        actor.state_ledger._entries = (state(91),)
        references = ref(owner), ref(actor), ref(actor.state_ledger)
        detach_actor(owner, -1)
        del owner, actor
        gc.collect()
        self.assertTrue(all(item() is None for item in references))


if __name__ == "__main__":
    unittest.main()
