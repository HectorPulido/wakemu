"""Actual constructor scopes contribute ephemeral state membership only."""
from copy import deepcopy
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_retained_registration_scope import (
    native_membership_owner,
    live_registration_scope,
)
from wakfu_server.combat_state_membership import membership_live, membership_actor_live
from wakfu_server.combat_summon_initialization import (
    detached_summon_scope,
    detached_actors,
)
from wakfu_server.combat_runtime_adapter import NativeActorAuthority


def state(uid):
    return RunningState(uid, 1, 1, -1, -1, -1, "target", False, (), 0, True, None)


def authority(identity):
    return NativeActorAuthority(
        targeting={"dpu_id": identity, "dpr_id": identity, "bcN": -1},
        is_player=False,
        deck_spell_ids=frozenset(),
        excluded_deck_spell_ids=frozenset(),
        is_carried=False,
        breed_id=1,
        summon_count=0,
        summon_counts_by_breed={},
        occupant_blocks=False,
        native_controller_id=identity,
    )


class DetachedMembershipScopeTests(unittest.TestCase):
    def fixture(self):
        owner = RetainedCollections()
        fight = Fight.__new__(Fight)
        fight.actors = owner.actors
        fight.native_retained_records = owner.records
        fight.native_retained_order = owner.order
        for name, rows in (*owner.sources.items(), *owner.area_sources.items()):
            setattr(fight, name, rows)
        return owner, fight

    def actor(self, identity, uid):
        actor = Actor(identity, 0, (0, 0, 0), 10, 6, 3, 1, 1)
        actor.team = -1  # Native detached construction precedes team assignment.
        actor.state_ledger._entries = (state(uid),)
        return actor

    def test_nested_exception_restores_context_and_operation_entry_presence(self):
        owner, fight = self.fixture()
        first, second = self.actor(-1, 91), self.actor(-2, 92)
        with live_registration_scope(owner) as outer:
            with detached_summon_scope(fight, first, authority(-1)):
                self.assertIs(native_membership_owner(fight), owner)
                self.assertNotIn(91, outer)
                with live_registration_scope(owner) as inner:
                    with self.assertRaisesRegex(RuntimeError, "native failure"):
                        with detached_summon_scope(fight, second, authority(-2)):
                            self.assertEqual(set(membership_live(owner)), {91, 92})
                            self.assertEqual(set(membership_actor_live(owner)), set())
                            raise RuntimeError("native failure")
                    self.assertIn(91, inner)
                    self.assertNotIn(92, inner)
                self.assertEqual(detached_actors(fight), (first,))
            self.assertEqual(detached_actors(fight), ())
        self.assertEqual(set(membership_live(owner)), set())
        self.assertEqual(owner.detached_actors, {})

    def test_actual_actor_promotion_preserves_membership_after_scope_exit(self):
        owner, fight = self.fixture()
        actor = self.actor(-1, 91)
        with detached_summon_scope(fight, actor, authority(-1)):
            fight.actors[-1] = actor
            self.assertIs(fight.actors[-1], actor)
            self.assertEqual(set(membership_actor_live(owner)), {91})
            actor.state_ledger._entries = (state(92),)
            self.assertEqual(set(membership_live(owner)), {92})
        self.assertEqual(set(membership_live(owner)), {92})
        self.assertEqual(set(membership_actor_live(owner)), {92})
        self.assertEqual(owner.detached_actors, {})

    def test_clone_excludes_context_and_cleanup_uses_original_identity(self):
        owner, fight = self.fixture()
        actor = self.actor(-1, 91)
        with detached_summon_scope(fight, actor, authority(-1)):
            cloned = deepcopy(owner)
            self.assertEqual(cloned.detached_actors, {})
            self.assertEqual(set(membership_live(cloned)), set())
            actor.id = -2
            self.assertIsNone(native_membership_owner(fight))
        self.assertEqual(set(membership_live(owner)), set())
        self.assertEqual(owner.detached_actors, {})


if __name__ == "__main__":
    unittest.main()
