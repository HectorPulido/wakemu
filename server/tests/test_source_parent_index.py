"""Actual-source aliases and parent-count changes; no retained metadata input."""
from copy import deepcopy
import unittest
from wakfu_server.combat_source_parent_index import (
    OwnedStateSourceRow,
    SourceParentIndex,
    SOURCE_MAPS,
)


def maps():
    return {name: {} for name in SOURCE_MAPS}


class SourceParentIndexTests(unittest.TestCase):
    def test_native_row_alias_parent_changes_and_last_user(self):
        sources = maps()
        first = OwnedStateSourceRow(uid=1, state_uid=100)
        second = OwnedStateSourceRow(uid=2, state_uid=100)
        name = "owned_stat_effects"
        sources[name].update({1: first, 2: second})
        index = SourceParentIndex(sources)
        self.assertIs(sources[name][1], first)
        self.assertEqual(set(index.parents(sources)), {100})
        self.assertEqual(index.counts[100], 2)
        first["state_uid"] = 200  # Update through the original native alias.
        self.assertEqual(set(index.parents(sources)), {100, 200})
        first.update(state_uid=300)
        self.assertEqual(set(index.parents(sources)), {100, 300})
        second.pop("state_uid")
        self.assertEqual(set(index.parents(sources)), {None, 300})
        first.__init__(state_uid=400)
        self.assertEqual(set(index.parents(sources)), {None, 400})
        del sources[name][1]
        index.bind(name, 1)
        self.assertEqual(set(index.parents(sources)), {None})
        first["state_uid"] = 500  # A detached historical alias is not a user.
        self.assertEqual(set(index.parents(sources)), {None})

    def test_unmatched_rows_opaque_fallback_and_deepcopy_preserve_ownership(self):
        sources = maps()
        index = SourceParentIndex(sources)
        name = "native_owned_group_effects"
        row = OwnedStateSourceRow(uid=1, state_uid=70, invocation={"level": 1})
        sources[name][1] = row
        index.bind(name, 1)
        # The native source exists before RetainedEffect registration.
        self.assertEqual(set(index.parents(sources)), {70})
        row["state_uid"] = []
        self.assertIsNone(index.parents(sources))
        row["state_uid"] = 71
        self.assertEqual(set(index.parents(sources)), {71})
        clone = deepcopy(sources)
        copied = SourceParentIndex(clone)
        self.assertIsNot(clone[name][1], row)
        clone[name][1]["state_uid"] = 72
        self.assertEqual(set(copied.parents(clone)), {72})
        self.assertEqual(set(index.parents(sources)), {71})
        opaque = {"uid": 2, "state_uid": 80}
        sources[name][2] = opaque
        index.bind(name, 2)
        self.assertIs(sources[name][2], opaque)
        self.assertIsNone(index.parents(sources))
        del sources[name][2]
        index.bind(name, 2)
        self.assertEqual(set(index.parents(sources)), {71})
        replacement = dict(sources, **{name: dict(sources[name])})
        self.assertIsNone(index.parents(replacement))
