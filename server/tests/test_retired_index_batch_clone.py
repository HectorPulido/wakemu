"""Private root transfers obey metadata copy and later callback boundaries."""
from copy import deepcopy
from types import SimpleNamespace
import sys
from wakfu_server import combat_retained_collections as storage
from wakfu_server.combat_owned_container_facts import OwnedContainerFacts
from wakfu_server.combat_retired_area_tracking import RetiredAreaTracking
import unittest
from unittest.mock import patch
from wakfu_server.combat_retained_collections import RetainedCollections, TrackedRow


class RetiredIndexBatchCloneTests(unittest.TestCase):
    def owner(self):
        owner = RetainedCollections()
        owner.records.install_owned(11, dict(uid=11, manager_id=-1, caster_id=-2))
        owner.retired_tracking._record(owner, 11)
        owner.retired_tracking.records_dirty.clear()
        return owner

    def test_native_batch_clone_dirty_roots_isolation_and_callback_fallback(self):
        # The real adapter plan consumes copied metadata lazily. Disabling only
        # the new batch proof recovers the previous full-dirty clone behavior.
        source = self.owner()
        source.records.install_owned(12, dict(uid=12, manager_id=-1, caster_id=-3))
        source.retired_tracking._record(source, 12)
        source.retired_tracking.records_dirty.clear()
        source.retired_tracking.bind_facts(OwnedContainerFacts())
        # Deleted historical rows are absent from a fresh clone. Their source
        # journal and stale tokens must not introduce extra clone work/roots.
        for uid in range(1000, 1408):
            source.retired_tracking.graph.root(("record", uid), {-9: 1})
            source.retired_tracking.records_dirty.add(uid)
        with patch.object(storage, "_native_record_clone_batch", return_value=False):
            legacy = deepcopy(source)
        copied = deepcopy(source)

        def refresh(owner):
            calls = []
            code = RetiredAreaTracking._record.__code__
            previous = sys.getprofile()

            def observe(frame, event, arg):
                if event == "call" and frame.f_code is code:
                    calls.append(frame.f_locals["uid"])

            try:
                sys.setprofile(observe)
                result = owner.retired_tracking.plan(
                    SimpleNamespace(
                        native_owned_state_containers=owner.retired_tracking.facts
                    )
                )
            finally:
                sys.setprofile(previous)
            return result, calls

        actual, calls = refresh(copied)
        expected, legacy_calls = refresh(legacy)
        self.assertEqual(actual, expected)
        self.assertEqual(calls, [])
        self.assertCountEqual(legacy_calls, [11, 12])
        self.assertEqual(
            copied.retired_tracking.graph.roots, legacy.retired_tracking.graph.roots
        )
        source.records[12]["caster_id"] = -4
        dirty = deepcopy(source)
        self.assertEqual(dirty.retired_tracking.records_dirty, {12})
        _, dirty_calls = refresh(dirty)
        self.assertEqual(dirty_calls, [12])
        self.assertEqual(dirty.retired_tracking.graph.roots[-4], 1)
        dirty.records[11]["caster_id"] = -5
        self.assertEqual(source.records[11]["caster_id"], -2)
        self.assertEqual(dirty.retired_tracking.records_dirty, {11})
        deleted = deepcopy(source)
        del deleted.records[11]
        self.assertIn(11, deleted.retired_tracking.records_dirty)
        after_delete = deepcopy(deleted)
        self.assertNotIn(11, after_delete.retired_tracking.records_dirty)
        self.assertNotIn(("record", 11), after_delete.retired_tracking.graph.tokens)
        self.assertNotIn(("record", 12), after_delete.retired_tracking.graph.tokens)
        _, after_delete_calls = refresh(after_delete)
        self.assertEqual(after_delete_calls, [12])
        self.assertNotIn(("record", 11), after_delete.retired_tracking.graph.tokens)
        self.assertIn(("record", 11), source.retired_tracking.graph.tokens)
        print(
            "retired_record_rebuilds", len(legacy_calls), len(calls), len(dirty_calls)
        )

        owner = self.owner()
        copied, row = deepcopy((owner, owner.records[11]))
        self.assertIs(row, copied.records[11])
        self.assertIsNot(row, owner.records[11])
        self.assertFalse(copied.retired_tracking.records_dirty)
        self.assertEqual(
            copied.retired_tracking.graph.roots, owner.retired_tracking.graph.roots
        )
        token = ("record", 11)
        self.assertIsNot(
            copied.retired_tracking.graph.tokens[token],
            owner.retired_tracking.graph.tokens[token],
        )
        copied.records[11]["caster_id"] = -3
        self.assertEqual(copied.retired_tracking.records_dirty, {11})
        self.assertEqual(owner.records[11]["caster_id"], -2)
        for mode in ("dirty", "cold", "opaque", "reader"):
            owner = self.owner()
            if mode == "dirty":
                owner.records[11]["caster_id"] = -4
            elif mode == "cold":
                owner.retired_tracking.graph.tokens.clear()
            elif mode == "opaque":
                owner.retired_tracking.graph.opaque.add(token)
            else:
                owner.records[11].get = lambda *args: None
            copied = deepcopy(owner)
            if mode == "opaque":
                self.assertTrue(
                    token in copied.retired_tracking.graph.opaque
                    or 11 in copied.retired_tracking.records_dirty
                )
            else:
                self.assertEqual(copied.retired_tracking.records_dirty, {11}, mode)

        owner = self.owner()
        original_init = TrackedRow.__init__
        constructor_calls = []

        def self_restoring_init(row, new_owner, uid, value):
            original_init(row, new_owner, uid, value)
            new_owner.retired_tracking.record_changed(uid)
            constructor_calls.append(uid)
            TrackedRow.__init__ = original_init

        with patch.object(TrackedRow, "__init__", new=self_restoring_init):
            copied = deepcopy(owner)
        self.assertEqual(constructor_calls, [11])
        self.assertEqual(copied.retired_tracking.records_dirty, {11})
        self.assertNotIn(token, copied.retired_tracking.graph.tokens)

        for changed in ("get", "owner", "uid"):
            owner = self.owner()
            original_membership = RetainedCollections._membership_changed

            def opaque_membership(new_owner, uid):
                original_membership(new_owner, uid)
                cloned = new_owner.records[uid]
                if changed == "get":
                    cloned.get = lambda *args: None
                elif changed == "owner":
                    cloned.owner = owner
                else:
                    cloned.uid = uid + 1
                # A post-call identity check alone must not accept this callback.
                RetainedCollections._membership_changed = original_membership

            with patch.object(
                RetainedCollections, "_membership_changed", new=opaque_membership
            ):
                copied = deepcopy(owner)
            self.assertEqual(copied.retired_tracking.records_dirty, {11})
            self.assertNotIn(token, copied.retired_tracking.graph.tokens)
            copied.retired_tracking._record(copied, 11)
            self.assertIn(token, copied.retired_tracking.graph.opaque)

        for mutate_clone in (False, True):
            owner = self.owner()

            class Source:
                def __deepcopy__(self, memo):
                    target = memo[id(owner)] if mutate_clone else owner
                    target.records[11]["caster_id"] = -5
                    return {"state_uid": None}

            owner.sources["owned_stat_effects"][22] = Source()
            copied = deepcopy(owner)
            self.assertEqual(
                copied.records[11]["caster_id"], -5 if mutate_clone else -2
            )
            self.assertEqual(
                copied.retired_tracking.records_dirty, {11} if mutate_clone else set()
            )

        owner = self.owner()

        class TargetFacts:
            def __deepcopy__(self, memo):
                memo[id(owner)].retired_tracking.record_changed(11)
                return OwnedContainerFacts()

        owner.retired_tracking.facts = TargetFacts()
        copied = deepcopy(owner)
        self.assertIn(11, copied.retired_tracking.records_dirty)

        owner = self.owner()

        class Facts:
            def __deepcopy__(self, memo):
                owner.records[11]["caster_id"] = -6
                owner.retired_tracking._record(owner, 11)
                owner.retired_tracking.records_dirty.clear()
                return {}

        owner.retired_tracking.facts = Facts()
        copied = deepcopy(owner)
        self.assertEqual(copied.records[11]["caster_id"], -6)
        self.assertEqual(copied.retired_tracking.graph.roots[-6], 1)
        self.assertFalse(copied.retired_tracking.records_dirty)


if __name__ == "__main__":
    unittest.main()
