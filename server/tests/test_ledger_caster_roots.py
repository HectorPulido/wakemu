"""Incremental caster roots preserve UID membership and real ledger aliases."""
from dataclasses import replace
import unittest

from wakfu_server.combat_state import Actor
from wakfu_server.combat_state_ledger import StateLedger, RunningState
from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_state_membership import (
    attach_actor,
    attach_area,
    attach_detached,
    detach_detached,
    caster_roots,
    retired_ledger_dirty,
    membership_live,
    membership_actor_live,
    ledger_identity_changed,
)


def state(uid, caster, target=-1):
    return RunningState(
        uid, 1, 1, caster, target, -1, "target", False, (), 0, True, None
    )


class LedgerCasterRootTests(unittest.TestCase):
    def fixture(self):
        owner = RetainedCollections()
        actor = Actor(-1, 1, (0, 0, 0), 10, 6, 3, 1, 1)
        owner.actors[-1] = actor
        attach_actor(owner, -1, actor)
        return owner, actor

    def test_duplicate_casters_change_locally_without_changing_uid_membership(self):
        owner, actor = self.fixture()
        actor.state_ledger._entries = (state(91, 80), state(92, 80), state(93, None))
        self.assertEqual(dict(caster_roots(owner)), {80: 2})
        dirty, areas = retired_ledger_dirty(owner)
        self.assertEqual(dirty, {80})
        self.assertEqual(areas, set())
        dirty.clear()
        actor.state_ledger.remove(91)
        self.assertEqual(dict(caster_roots(owner)), {80: 1})
        self.assertEqual(dirty, {80})
        self.assertEqual(set(membership_live(owner)), {92, 93})

    def test_area_and_detached_casters_are_roots_but_not_actor_allocator_uids(self):
        owner, actor = self.fixture()
        row = OwnedAreaRow(uid=80, state_ledger=StateLedger(80))
        owner.area_sources["native_effect_areas"][80] = row
        attach_area(owner, 80, row, role="native_effect_areas")
        row["state_ledger"]._entries = (state(94, 81, 80),)
        summon = Actor(-2, 1, (1, 0, 0), 10, 6, 3, 1, 1)
        owner.detached_actors[-2] = summon
        attach_detached(owner, summon)
        summon.state_ledger._entries = (state(95, 81, -2),)
        self.assertEqual(dict(caster_roots(owner)), {81: 2})
        self.assertEqual(set(membership_actor_live(owner)), set())
        self.assertEqual(retired_ledger_dirty(owner)[1], {80})
        retired_ledger_dirty(owner)[1].clear()
        row["state_ledger"]._entries = ()
        detach_detached(owner, summon)
        owner.detached_actors.pop(-2)
        self.assertEqual(dict(caster_roots(owner)), {})
        self.assertEqual(retired_ledger_dirty(owner)[1], {80})

    def test_opaque_caster_or_ledger_identity_only_invalidates_caster_proof(self):
        owner, actor = self.fixture()
        actor.state_ledger._entries = (state(91, True),)
        self.assertIsNone(caster_roots(owner))
        self.assertEqual(set(membership_live(owner)), {91})
        other, actor = self.fixture()
        actor.state_ledger._entries = (state(92, 80),)
        actor.state_ledger.actor_id = -99
        ledger_identity_changed(actor.state_ledger)
        self.assertIsNone(caster_roots(other))
        self.assertEqual(set(membership_live(other)), {92})


if __name__ == "__main__":
    unittest.main()
