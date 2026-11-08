"""GC accepts current native storage, never detached owner-bearing aliases."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from test_retained_gc_boundary import RetainedGCBoundaryTests
from wakfu_server import combat_retained_gc_boundary as boundary
from wakfu_server.combat_retained_collections import (
    bound_collections,
    OwnedOrder,
    TrackedRow,
)
from wakfu_server.combat_characteristic_link import bind_characteristic_stats
from wakfu_server.combat_runtime_messages import RuntimeMessages


class OwnedCollectionGCTests(unittest.TestCase):
    def fixture(self):
        boundary._CURSORS.clear()
        _, fight, _, dead, uid = RetainedGCBoundaryTests().fixture()
        # The shared tiny fixture replaces records/order for legacy coverage.
        # Restore the actual owner created by Fight, then use its native writer.
        owner = fight.actors.owner
        row = fight.native_retained_records[uid]
        fight.native_retained_records = owner.records
        fight.native_retained_order = owner.order
        owner.records.install_owned(uid, row)
        owner.order.append(uid)
        self.assertIs(bound_collections(vars(fight)), owner)
        self.assertTrue(owner.consistent())
        return deepcopy(fight), fight, RuntimeMessages(fight), dead, uid

    def test_actual_owned_preview_sweeps_and_preserves_indexes_and_original(self):
        previous, fight, runtime, dead, uid = self.fixture()
        owner = bound_collections(vars(fight))
        self.assertTrue(boundary._canonical_graph(fight))
        with patch.object(
            boundary, "_complete_view", wraps=boundary._complete_view
        ) as views:
            boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertEqual(views.call_count, 2)
        self.assertNotIn(uid, fight.native_retained_records)
        self.assertNotIn(uid, fight.native_owned_group_effects)
        self.assertIn(uid, previous.native_retained_records)
        self.assertIn(dead, fight.actors)
        self.assertIs(bound_collections(vars(fight)), owner)
        self.assertTrue(owner.consistent())

    def test_detached_rows_foreign_order_and_subclasses_are_not_canonical(self):
        _, fight, _, _, uid = self.fixture()
        row = fight.native_retained_records[uid]
        fight.detached = TrackedRow(row.owner, uid, dict(row))
        self.assertFalse(boundary._canonical_graph(fight))
        del fight.detached
        order = fight.native_retained_order
        fight.native_retained_order = OwnedOrder(order.owner)
        self.assertFalse(boundary._canonical_graph(fight))
        fight.native_retained_order = order

        class CustomRow(TrackedRow):
            pass

        fight.detached = CustomRow(row.owner, uid, dict(row))
        self.assertFalse(boundary._canonical_graph(fight))

    def test_actual_characteristic_binding_and_copy_are_canonical_but_foreign_binding_is_not(
        self,
    ):
        _, fight, _, _, _ = self.fixture()
        bind_characteristic_stats(fight)
        self.assertTrue(boundary._canonical_graph(fight))
        clone = deepcopy(fight)
        self.assertTrue(boundary._canonical_graph(clone))
        actor = next(iter(clone.actors.values()))
        self.assertIs(actor.effect_stats._fight, clone)
        actor.effect_stats._fight = fight
        self.assertFalse(boundary._canonical_graph(clone))


if __name__ == "__main__":
    unittest.main()
