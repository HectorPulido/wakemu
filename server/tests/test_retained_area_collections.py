"""Area roster gateways preserve Qq identity and native ledger membership."""
from copy import deepcopy
import unittest

from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_retained_collections import (
    RetainedCollections,
    bound_area_collections,
)
from wakfu_server.combat_retained_registration_scope import (
    native_membership_owner,
    live_registration_scope,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_ledger import StateLedger, RunningState
from wakfu_server.combat_state_membership import membership_live


def state(uid):
    return RunningState(uid, 1, 1, -1, -1, -1, "target", False, (), 0, True, None)


def fight(owner):
    result = Fight.__new__(Fight)
    result.actors = owner.actors
    result.native_retained_records = owner.records
    result.native_retained_order = owner.order
    for name, rows in (*owner.sources.items(), *owner.area_sources.items()):
        setattr(result, name, rows)
    return result


class RetainedAreaCollectionsTests(unittest.TestCase):
    def test_nonempty_native_area_maps_admit_current_membership(self):
        owner = RetainedCollections()
        target = fight(owner)
        row = OwnedAreaRow(uid=77)
        owner.area_sources["native_effect_areas"][77] = row
        self.assertIs(native_membership_owner(target), owner)
        row["state_ledger"] = StateLedger(77)
        row["state_ledger"]._entries = (state(91),)
        self.assertEqual(set(membership_live(owner)), {91})
        self.assertNotIn(77, owner.source_counts)
        self.assertIs(native_membership_owner(target), owner)

    def test_active_retired_and_actor_collisions_reject_only_while_present(self):
        owner = RetainedCollections()
        target = fight(owner)
        row = OwnedAreaRow(uid=77)
        active = owner.area_sources["native_effect_areas"]
        retired = owner.area_sources["native_retired_area_managers"]
        active[77] = row
        retired[77] = row
        self.assertIsNone(native_membership_owner(target))
        del active[77]
        self.assertIs(native_membership_owner(target), owner)
        owner.actors[77] = Actor(77, 1, (0, 0, 0), 10, 6, 3, 1, 1)
        self.assertIsNone(native_membership_owner(target))
        del owner.actors[77]
        self.assertIs(native_membership_owner(target), owner)

    def test_area_move_keeps_original_uid_presence_and_row_identity(self):
        owner = RetainedCollections()
        row = OwnedAreaRow(uid=77, state_ledger=StateLedger(77))
        row["state_ledger"]._entries = (state(91),)
        active = owner.area_sources["native_effect_areas"]
        retired = owner.area_sources["native_retired_area_managers"]
        active[77] = row
        with live_registration_scope(owner) as before:
            retired[77] = active.pop(77)
            self.assertIs(retired[77], row)
            row["state_ledger"]._entries = (state(92),)
            self.assertIn(91, before)
            self.assertNotIn(92, before)
        self.assertEqual(set(membership_live(owner)), {92})
        copied = deepcopy(owner)
        clone = copied.area_sources["native_retired_area_managers"][77]
        clone["state_ledger"]._entries = (state(93),)
        self.assertEqual(set(membership_live(copied)), {93})
        self.assertEqual(set(membership_live(owner)), {92})
        self.assertTrue(bound_area_collections(vars(fight(copied)), copied))

    def test_plain_external_row_preserves_alias_and_requests_fallback(self):
        owner = RetainedCollections()
        row = {"uid": 77, "state_ledger": StateLedger(77)}
        owner.area_sources["native_effect_areas"][77] = row
        self.assertIs(owner.area_sources["native_effect_areas"][77], row)
        self.assertIsNone(native_membership_owner(fight(owner)))


if __name__ == "__main__":
    unittest.main()
