"""Clone metadata validates once and retains actual ownership and fallback."""
from copy import deepcopy
import sys
import unittest
from unittest.mock import patch
from wakfu_server.combat_retained_collections import RetainedCollections, TrackedRow
from test_retained_collections import RetainedCollectionsTests


class RetainedCloneInstallTests(unittest.TestCase):
    def test_clone_single_key_validation_alias_mutation_and_custom_fallback(self):
        owner = RetainedCollections()
        fixture = RetainedCollectionsTests()
        fixture.install(owner, 11, -1)
        fixture.install(owner, 12, -2)
        self.assertTrue(owner.consistent())
        calls = []
        code = RetainedCollections._record_changed.__code__

        def profile(frame, event, arg):
            if event == "call" and frame.f_code is code:
                calls.append(frame.f_locals.get("_keys_checked"))

        previous = sys.getprofile()
        try:
            sys.setprofile(profile)
            clone, alias = deepcopy((owner, owner.records[11]))
        finally:
            sys.setprofile(previous)
        self.assertEqual(calls, [True, True])
        self.assertIs(alias, clone.records[11])
        self.assertIs(alias.owner, clone)
        self.assertTrue(clone.consistent())
        self.assertEqual(clone.managers, owner.managers)
        self.assertEqual(clone.retired_tracking.records_dirty, {11, 12})
        alias["manager_id"] = -3
        self.assertEqual(clone.manager_uids(-3), (11,))
        self.assertEqual(owner.manager_uids(-1), (11,))
        observed = []
        original_iter = TrackedRow.__iter__

        def iterator(row):
            observed.append(row.uid)
            return original_iter(row)

        with patch.object(TrackedRow, "__iter__", iterator):
            legacy = deepcopy(owner)
        self.assertEqual(observed, [11, 12])
        self.assertTrue(legacy.consistent())
        owner.records[11]["opaque"] = []
        with self.assertRaisesRegex(ValueError, "owned scalar facts"):
            deepcopy(owner)


if __name__ == "__main__":
    unittest.main()
