"""Owned source payload copying preserves deepcopy memo and callback semantics."""
from contextlib import nullcontext
from copy import deepcopy
import unittest
from unittest.mock import patch
from wakfu_server import combat_source_parent_index as source


class OwnedSourceScalarCopyTests(unittest.TestCase):
    def test_atomic_memo_cycles_callbacks_subclasses_and_parent_isolation(self):
        def copied(row, enabled, memo=None):
            with (
                nullcontext()
                if enabled
                else patch.object(source, "_copy_source_payload", deepcopy)
            ):
                return deepcopy(row, {} if memo is None else memo)

        # Explicit memo substitutions include None, which is a valid cached
        # result, not a sentinel for an absent entry.
        atom = 100012345
        text = "unique scalar memo leaf"
        for enabled in (False, True):
            row = source.OwnedStateSourceRow(
                number=atom, text=text, nullable=None, integer_key={atom: text}
            )
            clone = copied(
                row, enabled, {id(atom): None, id(text): "replacement", id(None): "nil"}
            )
            self.assertEqual(
                dict(clone),
                dict(
                    number=None,
                    text="replacement",
                    nullable="nil",
                    integer_key={None: "replacement"},
                ),
            )
            nested = {"leaf": [1, 2]}
            nested["cycle"] = nested
            row = source.OwnedStateSourceRow(first=nested, second=nested)
            row["self"] = row
            clone = copied(row, enabled)
            self.assertIs(clone["first"], clone["second"])
            self.assertIs(clone["first"]["cycle"], clone["first"])
            self.assertIs(clone["self"], clone)
            self.assertIsNot(clone["first"], nested)
            clone["first"]["leaf"].append(3)
            self.assertEqual(nested["leaf"], [1, 2])

        def callback_case(enabled, substitute_key):
            events = []

            class Key:
                def __deepcopy__(self, memo):
                    events.append(("key", memo["value_finished"]))
                    return "copied-key"

            key = Key()
            nested = {}

            class Value:
                def __deepcopy__(self, memo):
                    events.append(("value", True))
                    memo["value_finished"] = True
                    memo[id(nested)] = "temporary override"
                    if substitute_key:
                        memo[id(key)] = None
                    return "copied-value"

            nested[key] = Value()
            row = source.OwnedStateSourceRow(first=nested, second=nested)
            memo = {}
            clone = copied(row, enabled, memo)
            self.assertIs(clone["first"], clone["second"])
            self.assertIs(memo[id(nested)], clone["first"])
            self.assertTrue(any(value is nested for value in memo[id(memo)]))
            return dict(clone["first"]), events

        for substitute_key in (False, True):
            self.assertEqual(
                callback_case(True, substitute_key),
                callback_case(False, substitute_key),
            )

        events = []

        class Nested(dict):
            def __deepcopy__(self, memo):
                events.append("nested subclass")
                return {"custom": True}

        class Row(source.OwnedStateSourceRow):
            pass

        for row_type in (source.OwnedStateSourceRow, Row):
            row = row_type(nested=Nested(x=1))
            expected = copied(row, False)
            events.clear()
            if row_type is Row:
                with patch.object(
                    source,
                    "_copy_source_payload",
                    side_effect=AssertionError("subclass fastpath"),
                ):
                    actual = deepcopy(row)
            else:
                actual = copied(row, True)
            self.assertEqual(actual, expected)
            self.assertIs(type(actual), row_type)
            self.assertEqual(events, ["nested subclass"])

        for enabled in (False, True):
            maps = {name: {} for name in source.SOURCE_MAPS}
            row = source.OwnedStateSourceRow(
                uid=1, state_uid=70, invocation={"level": 1}
            )
            maps["owned_stat_effects"][1] = row
            index = source.SourceParentIndex(maps)
            self.assertEqual(set(index.parents(maps)), {70})
            clone = copied(row, enabled)
            self.assertNotIn("_parent_watchers", vars(clone))
            cloned_maps = {name: {} for name in source.SOURCE_MAPS}
            cloned_maps["owned_stat_effects"][1] = clone
            cloned_index = source.SourceParentIndex(cloned_maps)
            self.assertEqual(set(cloned_index.parents(cloned_maps)), {70})
            clone["state_uid"] = 71
            self.assertEqual(set(cloned_index.parents(cloned_maps)), {71})
            self.assertEqual(set(index.parents(maps)), {70})
            row["state_uid"] = 72
            self.assertEqual(set(index.parents(maps)), {72})
            self.assertEqual(set(cloned_index.parents(cloned_maps)), {71})
