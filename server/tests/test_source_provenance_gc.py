"""GC compatibility checks hidden key-proof fields without invoking custom getters."""
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from wakfu_server.combat_retained_gc_boundary import _canonical_graph
from wakfu_server.combat_source_provenance_entries import SourceProvenanceEntries


class SourceProvenanceGCTests(unittest.TestCase):
    def test_primitive_bookkeeping_aliases_and_hidden_reference_rejection(self):
        row = {"uid": 1, "parent_state_uid": None}
        entries = SourceProvenanceEntries({"1": row, "2": row})
        fight = SimpleNamespace(
            actors={}, native_state_source_provenance={"entries": entries}
        )
        self.assertTrue(_canonical_graph(fight))
        entries[3] = row
        del entries[3]
        self.assertFalse(entries.keys_are_native)
        self.assertTrue(
            _canonical_graph(fight)
        )  # Revocation is primitive, not a hidden root.
        entries.hidden_actor = object()
        self.assertFalse(_canonical_graph(fight))
        del entries.hidden_actor
        entries["3"] = object()
        self.assertFalse(_canonical_graph(fight))
        del entries["3"]
        reads = []

        def getter(self, name):
            reads.append(name)
            raise AssertionError("Custom provenance getter must not execute")

        with patch.object(SourceProvenanceEntries, "__getattribute__", getter):
            self.assertFalse(_canonical_graph(fight))
        self.assertEqual(reads, [])
