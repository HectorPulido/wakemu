"""Actual Qq alias mutation and ledger lifetime, without native catalog loading."""
from copy import deepcopy
import unittest

from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_state_ledger import StateLedger, RunningState
from wakfu_server.combat_state_membership import (
    attach_area,
    detach_area,
    membership_live,
    membership_actor_live,
)

ACTIVE = "native_effect_areas"
RETIRED = "native_retired_area_managers"


def ledger(uid):
    value = StateLedger(80)
    value._entries = (
        RunningState(uid, 1, 1, -1, 80, -1, "target", False, (), 0, True, None),
    )
    return value


class AreaMembershipGatewayTests(unittest.TestCase):
    def setup_row(self):
        owner = RetainedCollections()
        if not hasattr(owner, "area_sources"):
            owner.area_sources = {ACTIVE: {}, RETIRED: {}}
        row = OwnedAreaRow(uid=80, native_running_effect_manager=True)
        owner.area_sources[ACTIVE][80] = row
        attach_area(owner, 80, row, role=ACTIVE)
        return owner, row

    def test_null_then_live_ledger_is_seen_through_original_row_alias(self):
        owner, row = self.setup_row()
        alias = row
        self.assertEqual(set(membership_live(owner)), set())
        alias["state_ledger"] = ledger(91)
        self.assertIs(owner.area_sources[ACTIVE][80], alias)
        self.assertEqual(set(membership_live(owner)), {91})
        old = alias["state_ledger"]
        alias.update(state_ledger=ledger(92))
        old._entries = ledger(93)._entries
        self.assertEqual(set(membership_live(owner)), {92})
        alias.pop("state_ledger")
        self.assertEqual(set(membership_live(owner)), set())

    def test_live_to_retired_preserves_ledger_until_actual_prune(self):
        owner, row = self.setup_row()
        row["state_ledger"] = ledger(91)
        del owner.area_sources[ACTIVE][80]
        detach_area(owner, 80, role=ACTIVE)
        owner.area_sources[RETIRED][80] = row
        attach_area(owner, 80, row, role=RETIRED)
        row["state_ledger"]._entries = ledger(92)._entries
        self.assertEqual(set(membership_live(owner)), {92})
        del owner.area_sources[RETIRED][80]
        detach_area(owner, 80, role=RETIRED)
        row["state_ledger"]._entries = ledger(93)._entries
        self.assertEqual(set(membership_live(owner)), set())

    def test_area_state_uid_does_not_change_actor_only_allocator_membership(self):
        owner, row = self.setup_row()
        row["state_ledger"] = ledger(91)
        self.assertEqual(set(membership_live(owner)), {91})
        self.assertEqual(set(membership_actor_live(owner)), set())

    def test_deepcopy_rebind_preserves_new_row_and_leaves_old_index_unchanged(self):
        owner, row = self.setup_row()
        row["state_ledger"] = ledger(91)
        copied = deepcopy(row)
        other, unused = self.setup_row()
        other.area_sources[ACTIVE][80] = copied
        attach_area(other, 80, copied, role=ACTIVE)
        copied["state_ledger"]._entries = ledger(92)._entries
        self.assertEqual(set(membership_live(other)), {92})
        self.assertEqual(set(membership_live(owner)), {91})


if __name__ == "__main__":
    unittest.main()
