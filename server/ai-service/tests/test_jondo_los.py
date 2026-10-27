"""Advisory source-QK exclusions preserve native cast-ray blocker semantics."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_ai.bridge.jondo_los import casting_visible
from wakfu_server.combat_los import authoritative_visible


class JondoCastLOSTests(unittest.TestCase):
    def test_prepared_terrain_retains_live_source_exclusions_and_target_side_height(
        self,
    ):
        from wakfu_server.combat_los_geometry import prepare_los_geometry

        fight, source, _, footprints, probes = self.fixture()
        token = prepare_los_geometry(1134, fight.walkable)
        probes = frozenset({(-5, -7), (-6, -7)})
        fight.actors[7].native_los_height = 18
        footprints[7] = {(-8, -7), (-7, -7)}
        with patch(
            "wakfu_server.combat_los.protocol_catalog.exists", return_value=True
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((True, probes),),
        ) as rays:
            self.assertTrue(
                casting_visible(
                    1134,
                    source,
                    (-7, -7, -1),
                    fight,
                    blocking_footprints=footprints,
                    prepared_geometry=token,
                )
            )
            self.assertEqual(rays.call_args.kwargs["target_height"], 18)
            fight.native_qi_visibility_ignored_slots.append(2)
            fight.actors[7].native_los_height = 22
            self.assertTrue(
                casting_visible(
                    1134,
                    source,
                    (-7, -7, -1),
                    fight,
                    blocking_footprints=footprints,
                    prepared_geometry=token,
                )
            )
            self.assertEqual(rays.call_args.kwargs["target_height"], 22)

    def fixture(self):
        source, target = (-4, -7, -1), (-8, -7, -1)
        actors = {
            -7: SimpleNamespace(
                id=-7,
                hp=100,
                position=source,
                native_obstacle_id=1,
                native_los_height=8,
            ),
            7: SimpleNamespace(
                id=7, hp=100, position=target, native_obstacle_id=2, native_los_height=6
            ),
        }
        fight = SimpleNamespace(
            actors=actors,
            walkable={(x, -7, -1) for x in range(-8, -3)},
            native_qi_visibility_ignored_slots=[],
            native_los_ignored_affiliations=frozenset(),
        )
        footprints = {-7: {(-5, -7), (-4, -7), (-3, -7)}, 7: {(-8, -7)}}
        probes = frozenset({(-7, -7), (-6, -7), (-5, -7)})
        return fight, source, target, footprints, probes

    def test_large_source_body_is_ignored_without_mutating_source_or_blockers(self):
        fight, source, target, footprints, probes = self.fixture()
        before = deepcopy((vars(fight), footprints))
        with patch(
            "wakfu_server.combat_los.protocol_catalog.exists", return_value=True
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((True, probes), (True, probes)),
        ):
            self.assertFalse(
                authoritative_visible(
                    1134, source, target, fight, blocking_footprints=footprints
                )
            )
            self.assertTrue(
                casting_visible(
                    1134, source, target, fight, blocking_footprints=footprints
                )
            )
        self.assertEqual((vars(fight), footprints), before)

    def test_intermediate_enemy_body_and_static_walls_still_block(self):
        fight, source, target, footprints, probes = self.fixture()
        blocker = SimpleNamespace(
            id=9,
            hp=100,
            position=(-6, -7, -1),
            native_obstacle_id=3,
            native_los_height=6,
        )
        fight.actors[9] = blocker
        footprints[9] = {(-6, -7)}
        with patch(
            "wakfu_server.combat_los.protocol_catalog.exists", return_value=True
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((True, probes), (True, probes)),
        ):
            self.assertFalse(
                casting_visible(
                    1134, source, target, fight, blocking_footprints=footprints
                )
            )
            fight.native_qi_visibility_ignored_slots.append(3)
            self.assertTrue(
                casting_visible(
                    1134, source, target, fight, blocking_footprints=footprints
                )
            )
        with patch(
            "wakfu_server.combat_los.protocol_catalog.exists", return_value=True
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((False, probes), (False, probes)),
        ):
            self.assertFalse(
                casting_visible(
                    1134, source, target, fight, blocking_footprints=footprints
                )
            )

    def test_reverse_ray_ignores_its_own_source_but_keeps_large_target_body(self):
        fight, source, target, footprints, probes = self.fixture()
        with patch(
            "wakfu_server.combat_los.protocol_catalog.exists", return_value=True
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((True, probes), (True, probes)),
        ):
            self.assertTrue(
                casting_visible(
                    1134, source, target, fight, blocking_footprints=footprints
                )
            )
            self.assertFalse(
                casting_visible(
                    1134, target, source, fight, blocking_footprints=footprints
                )
            )

    def test_target_side_cell_uses_original_actor_height_without_moving_its_body(self):
        fight, source, center, footprints, _ = self.fixture()
        fight.actors[7].native_los_height = 18
        footprints[7] = {(-9, -7), (-8, -7), (-7, -7)}
        side = (-7, -7, -1)
        probes = frozenset({(-5, -7), (-6, -7)})
        before = deepcopy((vars(fight), footprints))

        def rays(map_id, ray_source, ray_target, *, source_height, target_height):
            self.assertEqual((map_id, ray_source, ray_target), (1134, source, side))
            self.assertEqual((source_height, target_height), (8, 18))
            return ((True, probes), (True, probes))

        with patch(
            "wakfu_server.combat_los.protocol_catalog.exists", return_value=True
        ), patch("wakfu_server.combat_native_los_ray.cast_rays", side_effect=rays):
            self.assertTrue(
                casting_visible(
                    1134, source, side, fight, blocking_footprints=footprints
                )
            )
        self.assertEqual(fight.actors[7].position, center)
        self.assertEqual((vars(fight), footprints), before)

    def test_side_cell_target_height_does_not_bypass_walls_or_another_actor(self):
        fight, source, _, footprints, _ = self.fixture()
        fight.actors[7].native_los_height = 18
        footprints[7] = {(-9, -7), (-8, -7), (-7, -7)}
        side = (-7, -7, -1)
        probes = frozenset({(-5, -7), (-6, -7)})
        fight.actors[9] = SimpleNamespace(
            id=9,
            hp=100,
            position=(-6, -7, -1),
            native_obstacle_id=3,
            native_los_height=6,
        )
        footprints[9] = {(-6, -7)}
        with patch(
            "wakfu_server.combat_los.protocol_catalog.exists", return_value=True
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((True, probes), (True, probes)),
        ):
            self.assertFalse(
                casting_visible(
                    1134, source, side, fight, blocking_footprints=footprints
                )
            )
        footprints[9] = set()
        with patch(
            "wakfu_server.combat_los.protocol_catalog.exists", return_value=True
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((False, probes), (False, probes)),
        ):
            self.assertFalse(
                casting_visible(
                    1134, source, side, fight, blocking_footprints=footprints
                )
            )

    def test_empty_aim_does_not_borrow_height_from_a_nearby_large_actor(self):
        fight, source, _, footprints, _ = self.fixture()
        fight.actors[7].native_los_height = 18
        footprints[7] = {(-9, -7), (-8, -7), (-7, -7)}
        empty = (-6, -6, -1)
        fight.walkable.add(empty)
        with patch(
            "wakfu_server.combat_los.protocol_catalog.exists", return_value=True
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((True, frozenset()),),
        ) as rays:
            self.assertTrue(
                casting_visible(
                    1134, source, empty, fight, blocking_footprints=footprints
                )
            )
        self.assertEqual(rays.call_args.kwargs["target_height"], 0)

    def test_ambiguous_target_body_and_incomplete_footprints_fail_closed(self):
        fight, source, target, footprints, _ = self.fixture()
        fight.actors[9] = SimpleNamespace(
            id=9,
            hp=100,
            position=(-9, -7, -1),
            native_obstacle_id=3,
            native_los_height=9,
        )
        footprints[9] = {target[:2], (-9, -7)}
        with self.assertRaisesRegex(ValueError, "unambiguous target body"):
            casting_visible(1134, source, target, fight, blocking_footprints=footprints)
        del footprints[9]
        with self.assertRaisesRegex(ValueError, "every living actor footprint"):
            casting_visible(1134, source, target, fight, blocking_footprints=footprints)

    def test_unknown_or_ambiguous_source_and_unproven_exclusions_are_rejected(self):
        fight, source, target, footprints, _ = self.fixture()
        for slots in (None, (), [True], [-1], [127]):
            fight.native_qi_visibility_ignored_slots = slots
            with self.subTest(slots=slots), self.assertRaises(ValueError):
                casting_visible(
                    1134, source, target, fight, blocking_footprints=footprints
                )
        fight.native_qi_visibility_ignored_slots = []
        fight.actors[-7].native_obstacle_id = None
        with self.assertRaises(ValueError):
            casting_visible(1134, source, target, fight, blocking_footprints=footprints)
        fight.actors[-7].native_obstacle_id = 1
        with self.assertRaises(ValueError):
            casting_visible(
                1134, (100, 100, 0), target, fight, blocking_footprints=footprints
            )
        fight.actors[9] = SimpleNamespace(
            id=9, hp=100, position=source, native_obstacle_id=3
        )
        with self.assertRaises(ValueError):
            casting_visible(1134, source, target, fight, blocking_footprints=footprints)


if __name__ == "__main__":
    unittest.main()
