"""Descriptor mutation cannot leave a native membership index authoritative."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_retained_registration_scope import native_membership_owner
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_ledger import StateLedger, RunningState
from wakfu_server.combat_state_membership import membership_live


def state(uid):
    return RunningState(uid, 1, 1, -1, -1, -1, "target", False, (), 0, True, None)


class MembershipDescriptorGuardsTests(unittest.TestCase):
    def test_actor_ledger_and_fight_source_descriptors_reject_stale_index(self):
        owner = RetainedCollections()
        fight = Fight.__new__(Fight)
        fight.actors = owner.actors
        fight.native_retained_records = owner.records
        fight.native_retained_order = owner.order
        for name, rows in (*owner.sources.items(), *owner.area_sources.items()):
            setattr(fight, name, rows)
        actor = Actor(-1, 0, (0, 0, 0), 10, 6, 3, 1, 1)
        actor.state_ledger._entries = (state(91),)
        owner.actors[-1] = actor
        replacement = StateLedger(-1)
        replacement._entries = (state(92),)
        runtime = SimpleNamespace(fight=fight)
        self.assertIs(native_membership_owner(fight), owner)
        with patch.object(
            Actor, "state_ledger", property(lambda self: replacement), create=True
        ):
            self.assertEqual(set(membership_live(owner)), {91})
            self.assertEqual(NativeRetainedRuntime._live(runtime), {92})
            self.assertIsNone(native_membership_owner(fight))
        with patch.object(
            Fight, "owned_stat_effects", property(lambda self: {93: {}}), create=True
        ):
            self.assertEqual(NativeRetainedRuntime._live(runtime), {91, 93})
            self.assertIsNone(native_membership_owner(fight))
        self.assertIs(native_membership_owner(fight), owner)


if __name__ == "__main__":
    unittest.main()
