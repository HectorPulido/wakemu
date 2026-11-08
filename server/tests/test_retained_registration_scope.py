"""Registration entry membership survives nested source/ledger mutations."""
import unittest

from wakfu_server.combat_state import Actor
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_state_membership import attach_actor
from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_retained_registration_scope import (
    live_registration_scope,
    registration_candidates,
)


class RegistrationScopeTests(unittest.TestCase):
    def setUp(self):
        self.owner = RetainedCollections()
        self.actor = Actor(-1, 1, (0, 0, 0), 10, 6, 3, 1, 1)
        self.owner.actors[-1] = self.actor
        attach_actor(self.owner, -1, self.actor)
        self.owner._notify_live_before = self.notify

    def notify(self, uid):
        for scope in getattr(self.owner, "_live_scopes", ()):
            scope.touch(uid)

    def source(self, uid, present):
        self.notify(uid)
        source = self.owner.sources["owned_stat_effects"]
        if present:
            source[uid] = {}
        else:
            source.pop(uid, None)

    def test_nested_creation_and_reuse_preserve_each_entry_membership(self):
        self.source(91, True)
        with live_registration_scope(self.owner) as outer:
            self.source(91, False)
            self.source(92, True)
            with live_registration_scope(self.owner) as inner:
                self.source(91, True)
                self.source(92, False)
                self.assertNotIn(91, inner)
                self.assertIn(92, inner)
            self.assertIn(91, outer)
            self.assertNotIn(92, outer)
        self.assertEqual(self.owner._live_scopes, [])

    def test_ledger_only_uid_and_pending_carrier_keep_entry_semantics(self):
        self.actor.state_ledger._entries = (
            RunningState(91, 1, 1, -1, -1, -1, "target", False, (), 0, True, None),
        )
        with live_registration_scope(self.owner) as outer:
            with live_registration_scope(self.owner, {91}) as inner:
                self.actor.state_ledger._entries = ()
                self.source(91, True)
                self.assertIn(91, outer)
                self.assertNotIn(91, inner)

    def test_exception_unwinds_inner_scope_only(self):
        with live_registration_scope(self.owner) as outer:
            with self.assertRaisesRegex(ValueError, "handler failure"):
                with live_registration_scope(self.owner):
                    raise ValueError("handler failure")
            self.assertEqual(self.owner._live_scopes, [outer])
        self.assertEqual(self.owner._live_scopes, [])

    def test_opaque_fallback_freezes_entry_without_admitting_new_uids(self):
        self.actor.state_ledger._entries = (
            RunningState(91, 1, 1, -1, -1, -1, "target", False, (), 0, True, None),
        )
        self.source(92, True)
        with live_registration_scope(self.owner) as journal:
            self.source(93, True)
            journal.freeze_membership()
            self.actor.state_ledger._entries = []
            self.source(92, False)
            self.source(94, True)
            self.assertIn(91, journal)
            self.assertIn(92, journal)
            self.assertNotIn(93, journal)
            self.assertNotIn(94, journal)
            self.assertNotIn(95, journal)

    def test_candidates_preserve_source_order_and_exclude_registered_rows(self):
        for uid in (93, 91, 92):
            self.source(uid, True)
        self.owner.records[91] = {"uid": 91, "manager_id": -1}
        self.assertEqual(
            registration_candidates(self.owner, "owned_stat_effects"), (93, 92)
        )
        self.source(93, False)
        self.source(93, True)
        self.assertEqual(
            registration_candidates(self.owner, "owned_stat_effects"), (92, 93)
        )


if __name__ == "__main__":
    unittest.main()
