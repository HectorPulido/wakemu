import unittest
from wakfu_server.combat_los import static_visible


class LOSTests(unittest.TestCase):
    def test_adjacent_native_ray(self):
        self.assertTrue(static_visible(1134, (-14, -10, -1), (-13, -10, -1)))

    def test_complete_native_topology_rejects_missing_surfaces(self):
        self.assertFalse(static_visible(1134, (999, 999, 0), (-13, -10, -1)))
        # Map9 now has complete native Vz columns, superseding the old
        # missing-map assumption. Preserve the native program result.
        from wakfu_server.combat_native_los_ray import static_ray

        self.assertEqual(
            static_visible(9, (-14, -10, -1), (-13, -10, -1)),
            static_ray(9, (-14, -10, -1), (-13, -10, -1))[0],
        )

    def test_native_intermediate_actor_blocks_but_endpoints_do_not(self):
        from types import SimpleNamespace
        from wakfu_server.combat_los import authoritative_visible

        source, target = (-14, -10, -1), (-11, -10, -1)
        fight = SimpleNamespace(
            actors={
                1: SimpleNamespace(
                    id=1,
                    hp=10,
                    team=0,
                    position=source,
                    native_los_height=6,
                    native_obstacle_id=None,
                ),
                2: SimpleNamespace(
                    id=2,
                    hp=10,
                    team=1,
                    position=target,
                    native_los_height=6,
                    native_obstacle_id=None,
                ),
                3: SimpleNamespace(
                    id=3,
                    hp=10,
                    team=1,
                    position=(-13, -10, -1),
                    native_los_height=6,
                    native_obstacle_id=None,
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
        # Complete native Vz columns supersede the old adjacent-only sample.
        from wakfu_server.combat_native_los_ray import static_ray

        self.assertEqual(
            static_visible(1385, (27, -25, 1), (27, -23, 1)),
            static_ray(1385, (27, -25, 1), (27, -23, 1))[0],
        )

    def test_other_map_native_actor_footprints_and_endpoint_probe_policy(self):
        from types import SimpleNamespace
        from wakfu_server.combat_los import authoritative_visible

        source, target = (27, -25, 1), (27, -24, 1)
        fight = SimpleNamespace(
            actors={
                i: SimpleNamespace(
                    id=i,
                    hp=10,
                    team=i - 1,
                    native_obstacle_id=None,
                    position=source if i == 1 else target,
                    native_los_height=6,
                )
                for i in (1, 2)
            },
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
