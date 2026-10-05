import unittest
from wakfu_server.combat_los import static_visible


class LOSTests(unittest.TestCase):
    def test_adjacent_native_ray(self):
        self.assertTrue(static_visible(1134, (-14, -10, -1), (-13, -10, -1)))

    def test_requires_exported_endpoints(self):
        self.assertFalse(static_visible(1134, (999, 999, 0), (-13, -10, -1)))
        with self.assertRaises(ValueError):
            static_visible(9, (-14, -10, -1), (-13, -10, -1))

    def test_native_intermediate_actor_blocks_but_endpoints_do_not(self):
        from types import SimpleNamespace
        from wakfu_server.combat_los import authoritative_visible

        source, target = (-14, -10, -1), (-11, -10, -1)
        fight = SimpleNamespace(
            actors={
                1: SimpleNamespace(
                    id=1, hp=10, team=0, position=source, native_los_height=6
                ),
                2: SimpleNamespace(
                    id=2, hp=10, team=1, position=target, native_los_height=6
                ),
                3: SimpleNamespace(
                    id=3, hp=10, team=1, position=(-13, -10, -1), native_los_height=6
                ),
            },
            walkable={(x, -10, -1) for x in range(-14, -10)},
        )
        footprints = {1: {source[:2]}, 2: {target[:2]}, 3: {(-13, -10)}}
        self.assertFalse(
            authoritative_visible(
                1134, source, target, fight, blocking_footprints=footprints
            )
        )
        footprints[3] = set()  # Explicit nonblocking native state.
        self.assertTrue(
            authoritative_visible(
                1134, source, target, fight, blocking_footprints=footprints
            )
        )
        with self.assertRaises(ValueError):
            authoritative_visible(
                1134, source, target, fight, blocking_footprints={1: set(), 2: set()}
            )

    def test_other_map_adjacent_native_ray_and_blocked_stair_ray(self):
        self.assertTrue(static_visible(1385, (27, -25, 1), (27, -24, 1)))
        self.assertFalse(static_visible(1385, (5, -21, 6), (6, -21, 1)))
        # Adjacent-only evidence cannot answer an unevaluated farther ray.
        with self.assertRaises(ValueError):
            static_visible(1385, (27, -25, 1), (27, -23, 1))

    def test_other_map_native_actor_footprints_and_endpoint_probe_policy(self):
        from types import SimpleNamespace
        from wakfu_server.combat_los import authoritative_visible

        source, target = (27, -25, 1), (27, -24, 1)
        fight = SimpleNamespace(
            actors={i: SimpleNamespace(id=i, hp=10, team=i - 1) for i in (1, 2)},
            walkable={source, target},
        )
        self.assertTrue(
            authoritative_visible(
                1385,
                source,
                target,
                fight,
                blocking_footprints={1: {source[:2]}, 2: {target[:2]}},
            )
        )
        with self.assertRaises(ValueError):
            authoritative_visible(
                1385, source, target, fight, blocking_footprints={1: set()}
            )
