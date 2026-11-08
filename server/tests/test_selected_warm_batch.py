"""Warm selected batches preserve fallback callbacks and query authority."""
import builtins
import unittest
from unittest.mock import patch
from wakfu_server import combat_selected_retained_values as selected
from wakfu_server import combat_retained_runtime as runtime
from wakfu_server.combat_retained_collections import TrackedRow
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_query import manager_query
from test_retained_indexed_query import fixture


class SelectedWarmBatchTests(unittest.TestCase):
    def test_warm_batch_method_proof_and_callback_invalidation(self):
        fight, _ = fixture()
        reader = selected.SelectedRetainedValues(fight, keep_current=False)
        row = fight.native_retained_records[10]
        expected = reader.read(fight, 10, row)
        ids = (10,) * 8
        with patch.object(
            selected, "getattr", wraps=builtins.getattr, create=True
        ) as calls:
            self.assertEqual(reader.read_batch(fight, ids, {10: row}), (expected,) * 8)
            self.assertEqual(calls.call_count, len(selected._ROW_VALUE_METHODS))
        self.assertEqual(manager_query(fight, 1).entries, (expected,))
        original = runtime._retained_record
        original_items = TrackedRow.items
        cold = dict(row)
        seen = []

        def construct(record):
            seen.append(record)
            if record is cold:
                TrackedRow.items = lambda self: dict.items(self)
            return original(record)

        try:
            with patch.object(runtime, "_retained_record", side_effect=construct):
                self.assertEqual(
                    reader.read_batch(fight, (10, 20), {10: cold, 20: row}),
                    (expected, expected),
                )
            self.assertTrue(any(value is row for value in seen))
        finally:
            TrackedRow.items = original_items
        reader.read(fight, 10, row)
        row.items = lambda: dict.items(row)
        try:
            with patch.object(runtime, "_retained_record", wraps=original) as calls:
                self.assertEqual(
                    reader.read_batch(fight, (10,), {10: row}), (expected,)
                )
                self.assertGreater(calls.call_count, 0)
        finally:
            del row.items
        replacement = dict(row, generic_effect=103)
        records = {10: dict(row), 20: row}
        first = records[10]

        def replace_later(record):
            if record is first:
                records[20] = replacement
            return original(record)

        with patch.object(runtime, "_retained_record", side_effect=replace_later):
            values = reader.read_batch(fight, (10, 20), records)
        self.assertEqual(values[1].generic_effect, 103)
        trace = []

        class CustomMap(dict):
            def __getitem__(self, uid):
                trace.append(uid)
                if uid == 20:
                    return replacement
                return dict.__getitem__(self, uid)

        values = reader.read_batch(fight, (10, 20), CustomMap({10: row, 20: row}))
        self.assertEqual(trace, [10, 20])
        self.assertEqual(values[1].generic_effect, 103)
        row["generic_effect"] = 102
        self.assertEqual(
            reader.read_batch(fight, (10,), {10: row})[0].generic_effect, 102
        )


if __name__ == "__main__":
    unittest.main()
