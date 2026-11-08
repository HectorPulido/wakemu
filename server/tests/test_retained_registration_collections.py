"""Registration journals consume actual native collection and ledger gateways."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from wakfu_server.combat_state import Actor
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_state_membership import membership_live
from wakfu_server.combat_retained_collections import (
    RetainedCollections,
    replace_collection,
    bind_adopted_actors,
)
from wakfu_server.combat_retained_registration_scope import (
    live_registration_scope,
    registration_candidates,
)


def state(uid):
    return RunningState(uid, 1, 1, -1, -1, -1, "target", False, (), 0, True, None)


def actor():
    return Actor(-1, 1, (0, 0, 0), 10, 6, 3, 1, 1)


def fight(owner):
    return SimpleNamespace(
        actors=owner.actors,
        native_retained_records=owner.records,
        native_retained_order=owner.order,
        **owner.sources
    )


class RegistrationCollectionsTests(unittest.TestCase):
    def test_source_reuse_pending_and_nested_scope_keep_entry_membership(self):
        owner = RetainedCollections()
        source = owner.sources["owned_stat_effects"]
        source[91] = {}
        source[92] = {}
        with live_registration_scope(owner, (92,)) as outer:
            del source[91]
            source[91] = {}
            source[93] = {}
            with live_registration_scope(owner) as inner:
                del source[93]
                self.assertIn(93, inner)
                self.assertNotIn(93, outer)
            self.assertIn(91, outer)
            self.assertNotIn(92, outer)
        self.assertEqual(owner._live_scopes, [])
        self.assertEqual(registration_candidates(owner, "owned_stat_effects"), (92, 91))

    def test_source_replacement_journals_cached_presence_before_counts(self):
        owner = RetainedCollections()
        owner.sources["owned_stat_effects"][91] = {}
        old_source = owner.sources["owned_stat_effects"]
        target = fight(owner)
        with live_registration_scope(owner) as before:
            replace_collection(target, "owned_stat_effects", {92: {}})
            self.assertIn(91, before)
            self.assertNotIn(92, before)
            old_source[93] = {}
            self.assertNotIn(93, owner.source_counts)
        self.assertEqual(registration_candidates(owner, "owned_stat_effects"), (92,))

    def test_actor_ledger_only_presence_and_actor_deletion_are_journaled(self):
        owner = RetainedCollections()
        current = actor()
        current.state_ledger._entries = (state(91),)
        owner.actors[-1] = current
        with live_registration_scope(owner) as before:
            current.state_ledger._entries = (state(92),)
            del owner.actors[-1]
            self.assertIn(91, before)
            self.assertNotIn(92, before)
            self.assertEqual(set(membership_live(owner)), set())
        current.state_ledger._entries = (state(93),)
        self.assertEqual(set(membership_live(owner)), set())

    def test_replacement_and_adoption_bind_actual_actor_objects(self):
        owner = RetainedCollections()
        current = actor()
        current.state_ledger._entries = (state(91),)
        owner.actors[-1] = current
        target = fight(owner)
        with live_registration_scope(owner) as before:
            old_map = owner.actors
            replace_collection(target, "actors", {})
            self.assertIn(91, before)
            self.assertEqual(set(membership_live(owner)), set())
        other = RetainedCollections()
        target.native_retained_records = other.records
        bind_adopted_actors(target, old_map)
        self.assertIs(target.actors, old_map)
        self.assertEqual(set(membership_live(other)), {91})
        current.state_ledger._entries = (state(92),)
        self.assertEqual(set(membership_live(other)), {92})
        self.assertEqual(set(membership_live(owner)), set())

    def test_opaque_ledger_fallback_keeps_entry_snapshot_and_new_uid_absence(self):
        owner = RetainedCollections()
        owner.actors[-1] = actor()
        owner.actors[-1].state_ledger._entries = (state(91),)
        source = owner.sources["owned_stat_effects"]
        source[92] = {}
        with live_registration_scope(owner) as before:
            source[93] = {}
            owner.actors[-1].state_ledger._entries = [state(94)]
            self.assertIsNone(membership_live(owner))
            del source[92]
            source[95] = {}
            self.assertIn(91, before)
            self.assertIn(92, before)
            self.assertNotIn(93, before)
            self.assertNotIn(94, before)
            self.assertNotIn(95, before)

    def test_deepcopy_has_fresh_membership_and_no_active_journal(self):
        owner = RetainedCollections()
        owner.actors[-1] = actor()
        owner.actors[-1].state_ledger._entries = (state(91),)
        with live_registration_scope(owner):
            cloned = deepcopy(owner)
        self.assertFalse(getattr(cloned, "_live_scopes", ()))
        cloned.actors[-1].state_ledger._entries = (state(92),)
        self.assertEqual(set(membership_live(cloned)), {92})
        self.assertEqual(set(membership_live(owner)), {91})


if __name__ == "__main__":
    unittest.main()
