"""Native UID reconciliation preserves pending and ledger-only membership."""
import unittest
from unittest.mock import patch

from wakfu_server.combat_retained_collections import (
    RetainedCollections,
    OwnedMap,
    OwnedOrder,
)
from wakfu_server.combat_retained_reconciliation import reconcile_registered_uids
from wakfu_server.combat_state import Actor
from wakfu_server.combat_state_ledger import RunningState


def state(uid):
    return RunningState(uid, 1, 1, -1, -1, -1, "target", False, (), 0, True, None)


def record(owner, uid):
    owner.records.install_owned(uid, {"uid": uid, "manager_id": -1})
    owner.order.append(uid)


class RetainedReconciliationTests(unittest.TestCase):
    def test_unchanged_population_does_not_traverse_sources_metadata_or_order(self):
        owner = RetainedCollections()
        for uid in range(20):
            owner.sources["owned_stat_effects"][uid] = {}
            record(owner, uid)
        with patch.object(
            OwnedMap, "__iter__", side_effect=AssertionError("global map scan")
        ):
            with patch.object(
                OwnedOrder, "__iter__", side_effect=AssertionError("global order scan")
            ):
                self.assertTrue(reconcile_registered_uids(owner, frozenset()))
        self.assertFalse(owner.order_dirty)

    def test_removed_source_keeps_ledger_only_uid_then_retires_last_membership(self):
        owner = RetainedCollections()
        current = Actor(-1, 1, (0, 0, 0), 10, 6, 3, 1, 1)
        current.state_ledger._entries = (state(91),)
        owner.actors[-1] = current
        record(owner, 91)
        owner.sources["state_wire_payloads"][91] = "wire"
        del owner.sources["state_wire_payloads"][91]
        self.assertTrue(reconcile_registered_uids(owner, frozenset()))
        self.assertIn(91, owner.records)
        current.state_ledger._entries = ()
        self.assertTrue(reconcile_registered_uids(owner, frozenset()))
        self.assertEqual(owner.records, {})
        self.assertEqual(owner.order, [])

    def test_pending_registered_uid_is_removed_even_while_source_present(self):
        owner = RetainedCollections()
        owner.sources["state_wire_payloads"][91] = "wire"
        record(owner, 91)
        self.assertTrue(reconcile_registered_uids(owner, frozenset({91})))
        self.assertEqual(owner.records, {})
        self.assertEqual(owner.order, [])
        self.assertIn(91, owner.sources["state_wire_payloads"])

    def test_invalid_order_requests_original_path_before_removal(self):
        owner = RetainedCollections()
        record(owner, 91)
        owner.order.append(92)
        self.assertFalse(reconcile_registered_uids(owner, frozenset()))
        self.assertIn(91, owner.records)
        self.assertEqual(owner.order, [91, 92])


if __name__ == "__main__":
    unittest.main()
