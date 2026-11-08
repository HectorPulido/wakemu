"""Native key ownership only; provenance row authority is deliberately fresh."""
from copy import copy, deepcopy
import unittest
from wakfu_server.combat_source_provenance_entries import SourceProvenanceEntries


class SourceProvenanceEntriesTests(unittest.TestCase):
    def test_native_mutators_preserve_original_row_aliases(self):
        first, second = {"uid": 1}, {"uid": 2}
        entries = SourceProvenanceEntries({"1": first})
        entries["2"] = second
        self.assertIs(entries.setdefault("1", {}), first)
        entries.update({"3": second}, fourth=first)
        entries |= {"5": first}
        entries.update(entries)
        self.assertTrue(entries.keys_are_native)
        first["parent_state_uid"] = 9
        self.assertEqual(entries["1"]["parent_state_uid"], 9)
        self.assertIs(entries["5"], first)
        self.assertIs(entries.pop("2"), second)
        self.assertEqual(entries.popitem(), ("5", first))
        del entries["3"]
        self.assertIsNone(entries.pop("missing", None))
        entries.clear()
        self.assertEqual(entries, {})
        self.assertTrue(entries.keys_are_native)
        made = SourceProvenanceEntries.fromkeys(("1", "2"), first)
        self.assertIs(made["1"], made["2"])
        self.assertTrue(made.keys_are_native)

    def test_foreign_keys_revoke_before_callbacks_and_eligibility_never_compares(self):
        for operation in ("set", "delete", "setdefault", "pop"):
            with self.subTest(operation=operation):
                entries = SourceProvenanceEntries({"1": {"uid": 1}})
                observed = []

                class Key(str):
                    def __hash__(self):
                        observed.append(entries.keys_are_native)
                        return str.__hash__(self)

                    def __eq__(self, other):
                        observed.append(entries.keys_are_native)
                        return str.__eq__(self, other)

                key = Key("1")
                if operation == "set":
                    entries[key] = {"uid": 2}
                elif operation == "delete":
                    del entries[key]
                elif operation == "setdefault":
                    entries.setdefault(key, {})
                else:
                    entries.pop(key)
                self.assertTrue(observed)
                self.assertEqual(set(observed), {False})
                before = list(observed)
                for _ in range(3):
                    self.assertFalse(entries.keys_are_native)
                self.assertEqual(observed, before)
                entries.clear()
                entries["2"] = {}
                self.assertFalse(entries.keys_are_native)
        entries = SourceProvenanceEntries()
        with self.assertRaises(TypeError):
            entries[[]] = {}
        self.assertFalse(entries.keys_are_native)

    def test_partial_failed_bulk_update_matches_dict_and_never_restores_proof(self):
        def rows():
            yield ("1", {"uid": 1})
            yield ("broken",)

        plain, owned = {}, SourceProvenanceEntries()
        with self.assertRaises(ValueError):
            plain.update(rows())
        with self.assertRaises(ValueError):
            owned.update(rows())
        self.assertEqual(owned, plain)
        self.assertFalse(owned.keys_are_native)
        owned.update({"2": {}})
        self.assertFalse(owned.keys_are_native)
        # Unknown mapping callbacks observe revocation before the first read.
        native = SourceProvenanceEntries()
        seen = []

        class Mapping:
            def keys(self):
                seen.append(native.keys_are_native)
                return ("3",)

            def __getitem__(self, key):
                seen.append(native.keys_are_native)
                return {"uid": 3}

        native.update(Mapping())
        self.assertEqual(seen, [False, False])
        self.assertEqual(native, {"3": {"uid": 3}})
        self.assertFalse(native.keys_are_native)

        class Keyword(str):
            pass

        keywords = SourceProvenanceEntries()
        keywords.update(**{Keyword("named"): {}})
        self.assertFalse(keywords.keys_are_native)
        # An invalid operation during an exact bulk update must not be hidden
        # by restoration of that bulk operation's initial eligibility flag.
        native = SourceProvenanceEntries()

        class PreviousValue:
            def __del__(self):
                native[1] = {"uid": 1}

        native["old"] = PreviousValue()
        native.update({"old": None})
        self.assertIn(1, native)
        self.assertFalse(native.keys_are_native)

    def test_copy_preserves_aliases_and_deepcopy_detaches_without_owner_graphs(self):
        row = {"uid": 1, "parent_state_uid": None}
        source = SourceProvenanceEntries({"1": row, "2": row})
        shallow = copy(source)
        self.assertIs(shallow["1"], row)
        self.assertTrue(shallow.keys_are_native)
        row["back"] = source
        clone = deepcopy(source)
        self.assertIs(type(clone), SourceProvenanceEntries)
        self.assertTrue(clone.keys_are_native)
        self.assertIs(clone["1"], clone["2"])
        self.assertIsNot(clone["1"], row)
        self.assertIs(clone["1"]["back"], clone)
        clone["1"]["parent_state_uid"] = 7
        self.assertIsNone(row["parent_state_uid"])
        self.assertEqual(set(vars(clone)), {"_native_keys", "_native_key_serial"})
        self.assertTrue(
            all(type(value) in (bool, int) for value in vars(clone).values())
        )
        poisoned = SourceProvenanceEntries()
        poisoned.update(iter((("1", row),)))
        self.assertFalse(copy(poisoned).keys_are_native)
        self.assertFalse(deepcopy(poisoned).keys_are_native)


if __name__ == "__main__":
    unittest.main()
