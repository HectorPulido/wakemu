"""Direct LOS inference is limited to exact, unconditional spell rules."""
import unittest
from types import SimpleNamespace

from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_snapshot import (
    direct_los_rule,
    native_static_los_receipt,
    native_static_los_target,
)


class DirectLosRuleTests(unittest.TestCase):
    def test_real_direct_unconditional_rule_is_certified(self):
        self.assertTrue(
            direct_los_rule(
                {
                    "line_of_sight": True,
                    "conditional": [],
                    "categories": [],
                }
            )
        )

    def test_conditional_rule_is_not_certified(self):
        self.assertFalse(
            direct_los_rule(
                {
                    "line_of_sight": True,
                    "conditional": ["target_state"],
                    "categories": [],
                }
            )
        )

    def test_missing_condition_or_category_evidence_is_not_certified(self):
        self.assertFalse(direct_los_rule({"line_of_sight": True, "categories": []}))
        self.assertFalse(direct_los_rule({"line_of_sight": True, "conditional": []}))

    def test_native_category_override_is_not_certified(self):
        self.assertFalse(
            direct_los_rule(
                {
                    "line_of_sight": True,
                    "conditional": [],
                    "categories": ["ignores_line_of_sight"],
                }
            )
        )

    def test_rule_without_native_los_is_not_certified(self):
        self.assertFalse(
            direct_los_rule(
                {
                    "line_of_sight": False,
                    "conditional": [],
                    "categories": [],
                }
            )
        )


class NativeStaticLosReceiptTests(unittest.TestCase):
    origin = (5, -21, 6)
    target = (6, -21, 1)
    candidate = SimpleNamespace(id=2, position=target, native_los_height=8)

    def target_identity(
        self,
        *,
        enabled=True,
        native_instance=1385,
        map_id=1385,
        actor_position=origin,
        origin=origin,
        ray_origin=origin,
        candidate=None
    ):
        return native_static_los_target(
            enabled,
            native_instance,
            map_id,
            1,
            actor_position,
            origin,
            ray_origin,
            self.target,
            self.candidate if candidate is None else candidate,
        )

    def test_map1385_target_height_eight_is_bound(self):
        self.assertEqual(self.target_identity(), 2)

    def test_map_or_actor_identity_mismatch_is_rejected(self):
        self.assertIsNone(self.target_identity(native_instance=1386))
        self.assertIsNone(self.target_identity(map_id=1386))
        self.assertIsNone(self.target_identity(enabled=False))

    def test_moved_origin_or_reverse_ray_is_rejected(self):
        self.assertIsNone(self.target_identity(actor_position=(4, -21, 6)))
        self.assertIsNone(self.target_identity(ray_origin=self.target))

    def test_height_nine_and_wrong_target_position_are_rejected(self):
        high = SimpleNamespace(id=2, position=self.target, native_los_height=9)
        displaced = SimpleNamespace(id=2, position=(7, -21, 1), native_los_height=8)
        self.assertIsNone(self.target_identity(candidate=high))
        self.assertIsNone(self.target_identity(candidate=displaced))

    def test_only_two_observed_blocked_rays_create_dto_triplet(self):
        identity = self.target_identity()
        indices = {self.origin: 18, self.target: 19}
        both_blocked = [(False, frozenset()), (False, frozenset())]

        self.assertEqual(
            native_static_los_receipt(
                indices, self.origin, self.target, identity, False, [both_blocked]
            ),
            [18, 19, 2],
        )
        self.assertIsNone(
            native_static_los_receipt(
                indices, self.origin, self.target, identity, False, []
            )
        )  # cache hit: no observation
        self.assertIsNone(
            native_static_los_receipt(
                indices,
                self.origin,
                self.target,
                identity,
                False,
                [[(False, frozenset())]],
            )
        )  # only one ray
        self.assertIsNone(
            native_static_los_receipt(
                indices,
                self.origin,
                self.target,
                identity,
                True,
                [[(True, frozenset()), (False, frozenset())]],
            )
        )  # one of the native alternatives is visible


if __name__ == "__main__":
    unittest.main()
