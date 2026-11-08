import copy
import sys
import unittest
from pathlib import Path

from wakfu_server.combat_source_provenance_entries import SourceProvenanceEntries


class ProvenanceScalarCopyTests(unittest.TestCase):
    def test_native_rows_copy_exactly_and_all_fallbacks_keep_aliases_and_callbacks(
        self,
    ):
        row = {
            "uid": 1001,
            "parent_state_uid": None,
            "parent_known": True,
            "container_known": True,
            "state_reference": 501,
            "state_level": 1,
            "caster_id": 7,
            "target_id": 8,
            "retained": True,
            "source": "captured_application",
            "container_present": False,
            "container_type": None,
            "container_id": None,
            "container_kind": None,
            "container_is_spell": None,
            "spell_protected": None,
        }
        entries = SourceProvenanceEntries()
        entries["1001"] = row
        entries["1002"] = row
        self.assertTrue(entries.keys_are_native)
        exact_copy_calls = []

        def profile(frame, event, arg):
            if event == "c_call" and getattr(arg, "__name__", None) == "copy":
                owner = getattr(arg, "__self__", None)
                if owner is row:
                    exact_copy_calls.append(owner)

        sys.setprofile(profile)
        try:
            first = copy.deepcopy({"entries": entries, "row": row, "alias": row})
        finally:
            sys.setprofile(None)
        self.assertEqual(len(exact_copy_calls), 1)
        self.assertIs(type(first["entries"]), SourceProvenanceEntries)
        self.assertTrue(first["entries"].keys_are_native)
        self.assertIs(first["entries"]["1001"], first["entries"]["1002"])
        self.assertIs(first["row"], first["alias"])
        self.assertIs(first["row"], first["entries"]["1001"])
        self.assertIsNot(first["row"], row)
        self.assertEqual(first["row"], row)
        first["row"]["state_level"] = 9
        self.assertEqual(row["state_level"], 1)

        # Reverse graph traversal still preserves one copied row identity.
        reverse = copy.deepcopy({"row": row, "alias": row, "entries": entries})
        self.assertIs(reverse["row"], reverse["entries"]["1002"])
        self.assertIs(reverse["row"], reverse["alias"])

        # Memo hits must use normal deepcopy semantics rather than row.copy().
        sentinel = object()
        memo = {id("captured_application"): sentinel}
        memo_copy = copy.deepcopy({"entries": entries}, memo)
        self.assertIs(memo_copy["entries"]["1001"]["source"], sentinel)
        self.assertIsNot(memo_copy["entries"]["1001"], row)

        calls = []

        class CustomRow(dict):
            def __deepcopy__(self, memo):
                calls.append("row")
                result = type(self)(self)
                memo[id(self)] = result
                result["payload"] = copy.deepcopy(self["payload"], memo)
                return result

        custom_row = CustomRow(payload=[1, 2])
        custom_entries = SourceProvenanceEntries({"1003": custom_row})
        custom_copy = copy.deepcopy(custom_entries)
        self.assertEqual(calls, ["row"])
        self.assertIs(type(custom_copy["1003"]), CustomRow)
        self.assertIsNot(custom_copy["1003"]["payload"], custom_row["payload"])

        # A callback in an earlier row mutates a later row; eligibility is
        # checked when that later row is reached, not cached from an earlier pass.
        later = {"uid": 1005, "value": 4}

        class MutateLater:
            def __deepcopy__(self, memo):
                later["value"] = [4]
                return self

        ordered = SourceProvenanceEntries(
            {"1004": {"uid": 1004, "value": MutateLater()}, "1005": later}
        )
        ordered_copy = copy.deepcopy(ordered)
        self.assertEqual(ordered_copy["1005"], later)
        self.assertIsNot(ordered_copy["1005"]["value"], later["value"])
        ordered_copy["1005"]["value"].append(5)
        self.assertEqual(later["value"], [4])

        # Cycles and nested mutable values retain normal deepcopy behavior.
        cyclic = {"uid": 1006, "payload": []}
        cyclic["self"] = cyclic
        cyclic_entries = SourceProvenanceEntries({"1006": cyclic})
        cyclic_copy = copy.deepcopy(cyclic_entries)
        self.assertIs(cyclic_copy["1006"]["self"], cyclic_copy["1006"])
        self.assertIsNot(cyclic_copy["1006"]["payload"], cyclic["payload"])

        # Ineligible keys revoke native-key proof and survive copy unchanged.
        opaque = SourceProvenanceEntries({"1007": {"uid": 1007}})
        opaque[7] = {"uid": 7}
        opaque_copy = copy.deepcopy(opaque)
        self.assertFalse(opaque.keys_are_native)
        self.assertFalse(opaque_copy.keys_are_native)
        self.assertEqual(opaque_copy, opaque)

        class CustomEntries(SourceProvenanceEntries):
            copied = 0

            def __deepcopy__(self, memo):
                type(self).copied += 1
                return {"custom": True}

        custom_map = CustomEntries({"1008": {"uid": 1008}})
        self.assertEqual(copy.deepcopy(custom_map), {"custom": True})
        self.assertEqual(CustomEntries.copied, 1)


if __name__ == "__main__":
    unittest.main()
