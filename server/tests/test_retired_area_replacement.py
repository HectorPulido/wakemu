"""Replacement preserves root journals without replaying unchanged native rows."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_retained_collections import (
    RetainedCollections,
    TrackedRow,
    replace_collection,
)


class RetiredAreaReplacementTests(unittest.TestCase):
    def test_unchanged_aliases_dirty_changes_and_opaque_rows(self):
        owner = RetainedCollections()
        fight = SimpleNamespace(native_retained_records=owner.records)
        for uid in range(1, 9):
            owner.records.install_owned(
                uid, dict(uid=uid, manager_id=-uid, caster_id=-99)
            )
        tracking = owner.retired_tracking

        def flush():
            for uid in tuple(tracking.records_dirty):
                tracking._record(owner, uid)
            tracking.records_dirty.clear()

        flush()
        expected = dict(tracking.graph.roots)
        original = owner.records
        manager_index = owner.by_manager
        original_bucket = owner.by_manager[-1]
        for _ in range(3):
            previous = owner.records
            with patch.object(
                owner, "_record_changed", wraps=owner._record_changed
            ) as changed:
                replace_collection(fight, "native_retained_records", dict(previous))
                self.assertEqual(changed.call_count, 0)
            self.assertIsNot(owner.records, previous)
            self.assertIs(owner.records[1], original[1])
            self.assertIs(owner.by_manager, manager_index)
            self.assertIs(owner.by_manager[-1], original_bucket)
            self.assertEqual(owner.by_manager[-1], {1})
            self.assertFalse(tracking.records_dirty)
            self.assertEqual(dict(tracking.graph.roots), expected)
        # Existing mutation notification survives replacement and alias identity.
        original[1]["caster_id"] = -100
        replace_collection(fight, "native_retained_records", dict(owner.records))
        self.assertEqual(tracking.records_dirty, {1})
        flush()
        self.assertEqual(tracking.graph.roots[-100], 1)
        # Removed UID, new UID and new payload object under an existing UID.
        old = owner.records
        replacement = dict(owner.records)
        replacement[2] = TrackedRow(owner, 2, dict(uid=2, manager_id=-22))
        replacement.pop(3)
        replacement[9] = TrackedRow(owner, 9, dict(uid=9, manager_id=-9))
        replace_collection(fight, "native_retained_records", replacement)
        self.assertEqual(tracking.records_dirty, {2, 3, 9})
        self.assertNotIn(3, owner.unmatched)
        self.assertIn(9, owner.unmatched)
        self.assertNotIn(3, owner.order_mismatch)
        self.assertIn(9, owner.order_mismatch)
        self.assertIsNot(owner.records[2], old[2])
        self.assertNotIn(-2, owner.by_manager)
        flush()
        self.assertNotIn(-3, tracking.graph.roots)
        self.assertNotIn(-3, owner.by_manager)
        self.assertEqual(owner.by_manager[-22], {2})
        self.assertEqual(owner.by_manager[-9], {9})
        self.assertEqual(tracking.graph.roots[-9], 1)
        # Foreign native rows and custom readers retain conservative notifications.
        foreign = RetainedCollections()
        foreign.records.install_owned(4, dict(uid=4, manager_id=-44))
        replacement = dict(owner.records)
        replacement[4] = foreign.records[4]
        replacement[9] = dict(uid=9, manager_id=-9)
        owner.records[5].get = lambda key, default=None: dict.get(
            owner.records[5], key, default
        )
        tracking.records_dirty.clear()
        replace_collection(fight, "native_retained_records", replacement)
        self.assertTrue({4, 5, 9} <= tracking.records_dirty)
        flush()
        self.assertTrue(
            {("record", 4), ("record", 5), ("record", 9)} <= tracking.graph.opaque
        )


if __name__ == "__main__":
    unittest.main()
