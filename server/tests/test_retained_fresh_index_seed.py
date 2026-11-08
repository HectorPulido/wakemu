"""Fresh scalar metadata seeding preserves indexes and callback fallbacks."""
from contextlib import nullcontext
from copy import deepcopy
import sys
import unittest
from unittest.mock import patch
from wakfu_server import combat_retained_collections as storage
from wakfu_server.combat_owned_container_facts import OwnedContainerFacts
from test_retired_index_batch_clone import RetiredIndexBatchCloneTests


class FreshIndexSeedTests(unittest.TestCase):
    def test_native_seed_indexes_aliases_mutations_and_callback_boundaries(self):
        def source():
            owner = storage.RetainedCollections()
            for uid, manager, parent in ((11, -1, None), (12, -1, 11), (13, -2, 11)):
                owner.records.install_owned(
                    uid,
                    dict(uid=uid, manager_id=manager, owner_uid=parent, caster_id=-3),
                )
                owner.order.append(uid)
                owner.retired_tracking._record(owner, uid)
            owner._refresh_order()
            owner.retired_tracking.records_dirty.clear()
            return owner

        def old_seed(owner, uid, payload):
            owner._record_changed(uid, _keys_checked=True)
            owner._membership_changed(uid)

        def copy(owner, enabled):
            counts = {"record": 0, "membership": 0}
            codes = {
                storage.RetainedCollections._record_changed.__code__: "record",
                storage.RetainedCollections._membership_changed.__code__: "membership",
            }
            previous = sys.getprofile()

            def observe(frame, event, arg):
                if event == "call" and frame.f_code in codes:
                    counts[codes[frame.f_code]] += 1

            with (
                nullcontext()
                if enabled
                else patch.object(storage, "_seed_fresh_record_indexes", old_seed)
            ):
                sys.setprofile(observe)
                try:
                    cloned, alias = deepcopy((owner, owner.records[12]))
                finally:
                    sys.setprofile(previous)
            self.assertIs(alias, cloned.records[12])
            self.assertIsNot(alias, owner.records[12])
            return cloned, counts

        def summary(owner):
            owner._refresh_order()
            return {
                name: deepcopy(getattr(owner, name))
                for name in (
                    "valid",
                    "by_manager",
                    "managers",
                    "by_owner_uid",
                    "record_owners",
                    "owner_opaque",
                    "unmatched",
                    "order_mismatch",
                    "ordinals",
                    "source_counts",
                )
            }, (
                deepcopy(owner.retired_tracking.graph.tokens),
                deepcopy(owner.retired_tracking.graph.roots),
                set(owner.retired_tracking.records_dirty),
            )

        original = source()
        old, before = copy(original, False)
        new, after = copy(original, True)
        self.assertEqual(summary(new), summary(old))
        self.assertEqual(before, {"record": 3, "membership": 3})
        self.assertEqual(after, {"record": 0, "membership": 0})
        self.assertEqual(new.owned_children(11), (12, 13))
        self.assertEqual(new.manager_uids(-1), (11, 12))
        for cloned in (old, new):
            cloned.records[12]["manager_id"] = -2
            cloned.records[13]["owner_uid"] = 12
            del cloned.records[11]
        self.assertEqual(summary(new), summary(old))
        self.assertEqual(original.records[12]["manager_id"], -1)
        self.assertEqual(original.records[13]["owner_uid"], 11)
        self.assertIn(11, original.records)
        print("fresh_metadata_index_callbacks", dict(baseline=before, candidate=after))

        # Facts are copied first and may legitimately populate the unpublished
        # owner's source and order indexes. Seed against their current values.
        def with_facts():
            owner = source()

            class Facts:
                def __deepcopy__(self, memo):
                    target = memo[id(owner)]
                    target.sources["state_wire_payloads"][11] = "native-test-payload"
                    target.order.append(11)
                    target._refresh_order()
                    owner.sources["state_wire_payloads"][12] = "source-side-effect"
                    return OwnedContainerFacts()

            owner.retired_tracking.facts = Facts()
            return owner

        old, _ = copy(with_facts(), False)
        new, _ = copy(with_facts(), True)
        self.assertEqual(summary(new), summary(old))
        self.assertNotIn(11, new.unmatched)
        self.assertNotIn(12, new.unmatched)

        # Primitive but invalid metadata stays invalid rather than acquiring
        # authoritative manager/owner buckets from the fast constructor.
        for field, value in (
            ("uid", True),
            ("manager_id", None),
            ("owner_uid", "opaque"),
        ):
            owner = source()
            owner.records[12][field] = value
            old, _ = copy(owner, False)
            new, _ = copy(owner, True)
            self.assertEqual(summary(new), summary(old), field)

        # Reuse the directly affected original clone regression: self-restoring
        # row constructor and membership hooks, warm/dirty/deleted root tokens,
        # aliases and later source/facts callbacks must all keep their fallback.
        RetiredIndexBatchCloneTests().test_native_batch_clone_dirty_roots_isolation_and_callback_fallback()
