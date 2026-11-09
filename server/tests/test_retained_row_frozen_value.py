"""Frozen selected values track actual row mutation without retaining authority."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from test_retained_indexed_query import fixture
from wakfu_server.combat_selected_retained_values import SelectedRetainedValues
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from wakfu_server import combat_retained_runtime as runtime
from wakfu_server import combat_retained_gc_boundary as boundary
from test_retained_gc_boundary import RetainedGCBoundaryTests


class RetainedRowFrozenValueTests(unittest.TestCase):
    def test_alias_changes_custom_readers_restore_and_gc_keep_fresh_authority(self):
        fight, _ = fixture()
        row = fight.native_retained_records[10]
        first = SelectedRetainedValues(fight, keep_current=False).read(fight, 10, row)
        with patch.object(
            runtime, "_retained_record", wraps=runtime._retained_record
        ) as convert:
            second = SelectedRetainedValues(fight, keep_current=False).read(
                fight, 10, row
            )
            self.assertIs(first, second)
            self.assertEqual(convert.call_count, 0)
            row["generic_effect"] = 102
            changed = SelectedRetainedValues(fight, keep_current=False).read(
                fight, 10, row
            )
            self.assertEqual(changed.generic_effect, 102)
            self.assertGreater(convert.call_count, 0)
        # Opaque getters may mutate their aliases directly; restoring them must
        # not revive an entry captured before the opaque interval.
        row.values = lambda: dict.values(row)
        dict.__setitem__(row, "generic_effect", 103)
        del row.values
        self.assertEqual(
            SelectedRetainedValues(fight).read(fight, 10, row).generic_effect, 103
        )

        def reentrant():
            SelectedRetainedValues(fight).read(fight, 10, row)
            yield ("generic_effect", 104)

        row.update(reentrant())
        self.assertEqual(
            SelectedRetainedValues(fight).read(fight, 10, row).generic_effect, 104
        )
        for plain in (dict(row), deepcopy(dict(row))):
            old = SelectedRetainedValues(fight).read(fight, 10, plain)
            plain["generic_effect"] = 105
            self.assertNotEqual(
                SelectedRetainedValues(fight).read(fight, 10, plain), old
            )
        row["definition_dispellable"] = True
        self.assertIs(
            SelectedRetainedValues(fight).read(fight, 10, row).definition_dispellable,
            True,
        )
        row["definition_dispellable"] = 1
        self.assertIs(
            type(
                SelectedRetainedValues(fight)
                .read(fight, 10, row)
                .definition_dispellable
            ),
            int,
        )
        row.pop("generic_effect")
        with self.assertRaises(TypeError):
            SelectedRetainedValues(fight).read(fight, 10, row)
        row["generic_effect"] = 104
        from wakfu_server.wakia_bridge.wakfu_ai.context.native_fingerprint import (
            fingerprint,
        )

        # Derived warm state is invisible to both native fingerprint and codec.
        object.__setattr__(row, "_retained_value", None)
        before = fingerprint(row)
        before_wire = encode_state(fight)
        SelectedRetainedValues(fight).read(fight, 10, row)
        self.assertEqual(fingerprint(row), before)
        self.assertEqual(encode_state(fight), before_wire)
        for current in (deepcopy(fight), decode_state(before_wire)):
            current_row = current.native_retained_records[10]
            self.assertIsNone(vars(current_row).get("_retained_value"))
            self.assertEqual(
                SelectedRetainedValues(current)
                .read(current, 10, current_row)
                .generic_effect,
                104,
            )

        previous, current, messages, dead, uid = RetainedGCBoundaryTests().fixture()
        owner = current.actors.owner
        metadata = current.native_retained_records[uid]
        current.native_retained_records = owner.records
        current.native_retained_order = owner.order
        owner.records.install_owned(uid, metadata)
        owner.order.append(uid)
        SelectedRetainedValues(current).read(current, uid, owner.records[uid])
        self.assertTrue(boundary._canonical_graph(current))
        boundary.prepare_retired_gc(previous, current, messages, ())
        self.assertNotIn(uid, current.native_retained_records)
        self.assertIn(dead, current.actors)
