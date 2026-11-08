"""Pending carrier scopes do not imply their source still exists."""
from itertools import product
import unittest
from wakfu_server.combat_retained_collections import RetainedCollections


class PendingConsistencyTests(unittest.TestCase):
    def owner(self, records, sources):
        owner = RetainedCollections()
        for uid in records:
            owner.records.install_owned(uid, dict(uid=uid, manager_id=7, target_id=7))
            owner.order.append(uid)
        for uid in sources:
            owner.sources["state_wire_payloads"][uid] = "00"
        return owner

    def test_effective_live_population_and_removed_pending_carrier(self):
        # Actual traced shape: 5095 was removed during its still-open scope;
        # nested5104 has published a wire source but not yet its retained row.
        owner = self.owner({1}, {1})
        self.assertTrue(owner.consistent({5095}))
        owner.sources["state_wire_payloads"][5104] = "00"
        self.assertTrue(owner.consistent({5095, 5104}))
        self.assertFalse(owner.consistent({5095}))
        del owner.sources["state_wire_payloads"][5104]
        self.assertTrue(owner.consistent({5095, 5104}))
        self.assertTrue(owner.consistent())
        # Native _live removes pending UIDs from the source union. Every
        # bounded configuration must retain exactly that same set equation.
        subsets = (set(), {1}, {2}, {1, 2})
        for records, sources, pending in product(subsets, repeat=3):
            current = self.owner(records, sources)
            self.assertEqual(
                current.consistent(pending),
                records == sources - pending,
                (records, sources, pending),
            )
            self.assertEqual(
                current.consistent(pending | {5095}), records == sources - pending
            )
        # No relaxation for malformed ownership, duplicate source families,
        # missing retained order, record-only rows or pending already registered.
        owner = self.owner({1}, {1})
        self.assertFalse(owner.consistent({1}))
        owner.sources["owned_stat_effects"][1] = {}
        self.assertFalse(owner.consistent({5095}))
        owner = self.owner({1}, {1})
        owner.order.clear()
        self.assertFalse(owner.consistent({5095}))
        owner = self.owner({1}, set())
        self.assertFalse(owner.consistent({1, 5095}))
        owner = self.owner(set(), set())
        owner.valid = False
        self.assertFalse(owner.consistent({5095}))


if __name__ == "__main__":
    unittest.main()
