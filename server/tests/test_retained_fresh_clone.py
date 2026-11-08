"""Fresh-row clone parity and callback-safe fallback regressions."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from wakfu_server import combat_retained_collections as module


def owner():
    result = module.RetainedCollections()
    for uid in (11, 12, 13):
        result.records.install_owned(
            uid,
            dict(
                uid=uid, manager_id=7, target_id=7, owner_uid=None if uid == 11 else 11
            ),
        )
        result.order.append(uid)
        result.sources["state_wire_payloads"][uid] = "wire"
    result.ordered_uids(7)
    return result


def index_snapshot(value):
    names = (
        "valid",
        "by_owner_uid",
        "record_owners",
        "owner_opaque",
        "by_manager",
        "managers",
        "live_keys",
        "source_counts",
        "source_ordinals",
        "source_next",
        "unmatched",
        "duplicate_sources",
        "ordinals",
        "order_mismatch",
        "order_dirty",
    )
    graph = value.retired_tracking.graph
    return (
        {name: getattr(value, name) for name in names},
        value.retired_tracking.records_dirty,
        graph.roots,
        graph.tokens,
        graph.opaque,
        graph.owners,
        list(value.order),
    )


class FreshCloneTests(unittest.TestCase):
    def test_fresh_clone_matches_batch_clone_indices_fields_and_aliases(self):
        source = owner()
        # The prior batch-clone path is the local behavioral baseline. Disabling
        # only the new fresh-row certificate preserves its ordinary callbacks.
        with patch.object(module, "_native_record_clone_batch", return_value=False):
            baseline = deepcopy(source)

        with patch.object(
            module,
            "_native_record_clone_batch",
            wraps=module._native_record_clone_batch,
        ) as proof:
            copied = deepcopy(source)
        self.assertEqual(2, proof.call_count)
        self.assertEqual(
            [False, True],
            [call.kwargs.get("finished", False) for call in proof.call_args_list],
        )
        self.assertEqual(index_snapshot(baseline), index_snapshot(copied))
        for uid in source.records:
            old, new = baseline.records[uid], copied.records[uid]
            self.assertEqual(dict(old), dict(new))
            self.assertEqual(list(vars(old)), list(vars(new)))
            self.assertIs(new.owner, copied)
            self.assertIsNot(new, source.records[uid])
            self.assertIsNone(new._retained_value)
            self.assertIsNone(new._scalar_eligibility)

        aliased_owner, aliased_row = deepcopy((source, source.records[12]))
        self.assertIs(aliased_row, aliased_owner.records[12])
        self.assertIs(aliased_row.owner, aliased_owner)
        self.assertIsNot(aliased_row, source.records[12])

        source_dirty = set(source.retired_tracking.records_dirty)
        copied.records[12]["manager_id"] = 9
        self.assertEqual(source.records[12]["manager_id"], 7)
        self.assertIn(12, copied.retired_tracking.records_dirty)
        self.assertEqual(source_dirty, source.retired_tracking.records_dirty)

    def test_opaque_source_callback_disables_fresh_rows_for_remainder(self):
        source = owner()
        events = []
        original = module.TrackedRow.__init__

        def custom_init(row, new_owner, uid, value):
            events.append(uid)
            original(row, new_owner, uid, value)

        class Opaque(dict):
            def __deepcopy__(self, memo):
                events.append("opaque")
                module.TrackedRow.__init__ = custom_init
                return dict(self)

        # Model an opaque legacy row without calling the active OwnedMap
        # mutation gateway; the owner remains eligible when clone starts.
        prior = list(source.records.items())
        dict.clear(source.records)
        dict.__setitem__(source.records, 10, Opaque(uid=10, manager_id=7))
        for uid, row in prior:
            dict.__setitem__(source.records, uid, row)
        target = module.RetainedCollections()
        self.assertTrue(module._native_record_clone_batch(source, target))

        try:
            copied = deepcopy(source)
        finally:
            module.TrackedRow.__init__ = original

        self.assertEqual(["opaque", 11, 12, 13], events)
        for uid in (11, 12, 13):
            self.assertIs(copied.records[uid].owner, copied)
            self.assertEqual(dict(copied.records[uid]), dict(source.records[uid]))
        self.assertIs(type(copied.records[10]), dict)
        self.assertEqual(source.records[11]["manager_id"], 7)

    def test_constructor_override_before_clone_uses_all_original_callbacks(self):
        source = owner()
        original = module.TrackedRow.__init__
        events = []

        def custom_init(row, new_owner, uid, value):
            events.append(uid)
            original(row, new_owner, uid, value)

        with patch.object(module.TrackedRow, "__init__", new=custom_init):
            copied = deepcopy(source)
        self.assertEqual([11, 12, 13], events)
        self.assertEqual(index_snapshot(source), index_snapshot(copied))
        for uid in source.records:
            self.assertIs(copied.records[uid].owner, copied)
            self.assertEqual(dict(copied.records[uid]), dict(source.records[uid]))


if __name__ == "__main__":
    unittest.main()
