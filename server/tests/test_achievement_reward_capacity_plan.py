"""Reward capacity preflight must conserve quantity and avoid partial grants."""
import copy
import unittest
from wakfu_server.achievements.rewards import _plan_item_capacity, RewardCapacity


class RewardCapacityPlanTests(unittest.TestCase):
    def test_full_base_bag_uses_secondary_bag_and_splits_overflow(self):
        bags = [dict(uid=1, capacity=1), dict(uid=2, capacity=2)]
        items = [dict(uid=8, container=1, slot=0, quantity=10)]
        merges, placements = _plan_item_capacity(bags, items, [], 15, 10)
        self.assertEqual(merges, [])
        self.assertEqual(
            [(b["uid"], s, q) for b, s, q in placements], [(2, 0, 10), (2, 1, 5)]
        )

    def test_merge_capacity_counts_even_without_empty_slots(self):
        bags = [dict(uid=1, capacity=1)]
        items = [dict(uid=8, container=1, slot=0, quantity=4)]
        before = copy.deepcopy(items)
        merges, placements = _plan_item_capacity(bags, items, items, 6, 10)
        self.assertEqual(merges, [(items[0], 6)])
        self.assertEqual(placements, [])
        self.assertEqual(items, before)

    def test_insufficient_capacity_does_not_mutate_merge_targets(self):
        bags = [dict(uid=1, capacity=1)]
        items = [dict(uid=8, container=1, slot=0, quantity=4)]
        before = copy.deepcopy(items)
        with self.assertRaises(RewardCapacity):
            _plan_item_capacity(bags, items, items, 7, 10)
        self.assertEqual(items, before)

    def test_incompatible_stack_is_not_used_as_free_space(self):
        bags = [dict(uid=1, capacity=1)]
        items = [dict(uid=8, container=1, slot=0, quantity=1)]
        with self.assertRaises(RewardCapacity):
            _plan_item_capacity(bags, items, [], 1, 10)


class CompletedTrackingTests(unittest.TestCase):
    def state(self, *, tracking=()):
        return dict(
            variables={},
            objectives=[],
            running=[],
            completed=[7],
            tracking=list(tracking),
            recent=[],
            completion_dates={},
        )

    def test_completed_achievement_enable_rejects_without_state_or_storage_mutation(
        self,
    ):
        from unittest.mock import patch
        from wakfu_server.achievements import service, wire

        state = self.state()
        before = copy.deepcopy(state)
        # Original bdM.r(true)->Bo rejects Bk(id), which reads bdD.aqc's
        # completion flag. Completing through bdM.q also removes tracking.
        with patch.object(service, "_owner"), patch.object(
            service.catalog, "load", return_value={"definitions": {7: {}}}
        ), patch.object(
            service.storage, "load_locked", return_value=state
        ), patch.object(
            service.storage, "store"
        ) as store:
            with self.assertRaisesRegex(ValueError, "Completed achievement"):
                service.track(object(), {"id": 5}, 7, True)
            store.assert_not_called()
        self.assertEqual(state, before)
        self.assertTrue(wire.section(state))

    def test_completed_achievement_disable_cleans_stale_tracking_and_encodes_false(
        self,
    ):
        import struct
        from unittest.mock import patch
        from wakfu_server.achievements import service

        state = self.state(tracking=(7,))
        before = copy.deepcopy(state)
        db = object()
        with patch.object(service, "_owner"), patch.object(
            service.catalog, "load", return_value={"definitions": {7: {}}}
        ), patch.object(
            service.storage, "load_locked", return_value=state
        ), patch.object(
            service.storage, "store"
        ) as store:
            packets = service.track(db, {"id": 5}, 7, False)
            store.assert_called_once_with(db, 5, state)
        self.assertEqual(state, dict(before, tracking=[]))
        self.assertEqual(packets, [(13371, struct.pack(">qiB", 5, 7, 0))])
