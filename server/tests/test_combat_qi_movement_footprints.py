import unittest

from wakfu_server.combat.combat_qi_fight import (
    install_fresh_actor_slots,
    prepare_fresh_actor_slots,
)
from wakfu_server.combat.combat_qi_surface_catalog import native_qi_surfaces
from wakfu_server.combat.combat_qi_surface_selection import native_surface_indices
from wakfu_server.combat.combat_terrain import map_geometry
from wakfu_server.combat.combat_wire import arena
from wakfu_server.combat.combat_state import Actor, Fight


class NativeQIMovementFootprintTests(unittest.TestCase):
    """Movement uses the actor's registered body at every native path step."""

    @classmethod
    def setUpClass(cls):
        geometry = map_geometry(902)
        cls.cells = frozenset(
            tuple(cell)
            for cell in geometry["cells"]
            if -40 <= cell[0] <= -33 and -32 <= cell[1] <= -25
        )
        cls.edges = frozenset(
            (tuple(start), tuple(end))
            for start, end in geometry["edges"]
            if tuple(start) in cls.cells and tuple(end) in cls.cells
        )
        cls.surfaces = native_qi_surfaces(902)

    def fight(self, mover_position, blocker_position, *, radii=(1, 0)):
        mover = Actor(
            7, 0, mover_position, 80, 6, 6, 100, 20, owner_id=1, controlled=True
        )
        blocker = Actor(187, 1, blocker_position, 40, 0, 0, 10, 10)
        mover.physical_radius, blocker.physical_radius = radii
        fight = Fight(
            902,
            [mover, blocker],
            self.cells,
            {0: {mover_position}, 1: {blocker_position}},
            self.edges,
        )
        selected = sorted(self.cells)
        fight.native_qi_snapshot = arena(
            902,
            1,
            selected,
            {0: {mover_position}, 1: {blocker_position}},
            surface_indices=native_surface_indices(self.surfaces, selected),
        )
        prepared = prepare_fresh_actor_slots(
            fight,
            physical_radii={
                actor_id: actor.physical_radius
                for actor_id, actor in fight.actors.items()
            },
        )
        install_fresh_actor_slots(fight, prepared)
        fight.phase = "active"
        fight.order = [mover.id, blocker.id]
        fight.turn_index = 0
        fight.turn_id = 1
        mover.turn_count = 1
        return fight, mover, blocker

    def test_large_body_cannot_cross_native_blocker_on_any_path_step(self):
        path = [(-37, -29, 0), (-37, -28, 0), (-36, -28, 0)]
        # The first case is the reported Shin/Larva movement. The second
        # blocker intersects only the middle step's body, not the path anchor
        # cells, starting body, or final body.
        for blocker_position in ((-36, -27, 0), (-38, -27, 0)):
            with self.subTest(blocker_position=blocker_position):
                fight, shin, blocker = self.fight(
                    (-37, -30, 0), blocker_position, radii=(1, 0)
                )
                before = (
                    shin.position,
                    shin.mp,
                    list(fight.native_qi_slots),
                    list(fight.native_qi_touched_cells),
                    len(fight.events),
                )
                with self.assertRaisesRegex(ValueError, "Invalid combat movement path"):
                    fight.move(1, shin.id, path)
                self.assertEqual(
                    (
                        shin.position,
                        shin.mp,
                        fight.native_qi_slots,
                        fight.native_qi_touched_cells,
                        len(fight.events),
                    ),
                    before,
                )
                self.assertEqual(blocker.position, blocker_position)

    def test_small_body_still_cannot_enter_large_registered_footprint(self):
        fight, small, large = self.fight((-39, -30, 0), (-37, -30, 0), radii=(0, 1))
        with self.assertRaisesRegex(ValueError, "Invalid combat movement path"):
            fight.move(1, small.id, [(-38, -30, 0)])
        self.assertEqual((small.position, small.mp), ((-39, -30, 0), 6))
        self.assertEqual(large.position, (-37, -30, 0))

    def test_large_actor_ignores_own_footprint(self):
        fight, mover, blocker = self.fight((-37, -30, 0), (-34, -27, 0), radii=(1, 0))
        # The mover's new body overlaps its own old QI cells. Own-slot
        # exclusion must allow the ordinary move.
        fight.move(1, mover.id, [(-37, -29, 0)])
        self.assertEqual(mover.position, (-37, -29, 0))

    def test_off_anchor_mask_precedes_override_and_ignored_slot_is_preserved(self):
        fight, mover, _ = self.fight((-37, -30, 0), (-34, -27, 0), radii=(1, 0))
        fight.native_qi_movement_override = True
        terrain = fight.native_qi_snapshot
        blocked_xy = (-38, -28)
        index = (blocked_xy[1] - terrain["y"]) * terrain["width"] + (
            blocked_xy[0] - terrain["x"]
        )
        terrain["cell_masks"][index] |= 768
        with self.assertRaisesRegex(ValueError, "Invalid combat movement path"):
            fight.move(1, mover.id, [(-37, -29, 0)])
        self.assertEqual((mover.position, mover.mp), ((-37, -30, 0), 6))

        # Restore fresh actors because the prior attempt deliberately used a
        # native terrain mask. biN exclusions still bypass obstacle occupancy
        # at an off-anchor cell of the mover's destination footprint.
        fight, mover, blocker = self.fight((-37, -30, 0), (-38, -28, 0), radii=(1, 0))
        fight.native_qi_ignored_slots = [blocker.native_obstacle_id]
        fight.move(1, mover.id, [(-37, -29, 0)])
        self.assertEqual(mover.position, (-37, -29, 0))

        # Restore a fresh registration to test native biP occupancy bypass
        # independently of the move above.
        fight, mover, blocker = self.fight((-37, -30, 0), (-36, -28, 0), radii=(1, 0))
        fight.native_qi_movement_override = True
        fight.move(1, mover.id, [(-37, -29, 0)])
        self.assertEqual(mover.position, (-37, -29, 0))

    def test_qi_occupancy_remains_xy_based_across_stacked_altitudes(self):
        mover = Actor(7, 0, (0, 0, 0), 50, 6, 3, 10, 10, owner_id=1, controlled=True)
        blocker = Actor(187, 1, (1, 0, 1), 30, 0, 0, 1, 10)
        mover.physical_radius = blocker.physical_radius = 0
        fight = Fight(
            903,
            [mover, blocker],
            {(0, 0, 0), (1, 0, 0), (1, 0, 1)},
            {0: {mover.position}, 1: {blocker.position}},
            {((0, 0, 0), (1, 0, 0))},
        )
        fight.native_qi_snapshot = {
            "x": 0,
            "y": 0,
            "width": 2,
            "height": 1,
            "cell_masks": [0, 0],
        }
        prepared = prepare_fresh_actor_slots(
            fight,
            physical_radii={
                actor_id: actor.physical_radius
                for actor_id, actor in fight.actors.items()
            },
        )
        install_fresh_actor_slots(fight, prepared)
        fight.phase = "active"
        fight.order = [mover.id, blocker.id]
        fight.turn_index = 0
        fight.turn_id = 1
        mover.turn_count = 1

        with self.assertRaisesRegex(ValueError, "Invalid combat movement path"):
            fight.move(1, mover.id, [(1, 0, 0)])
        self.assertEqual((mover.position, mover.mp), ((0, 0, 0), 3))

    def test_server_controlled_large_actor_uses_the_same_footprint_guard(self):
        fight, mover, _ = self.fight((-37, -30, 0), (-36, -27, 0), radii=(1, 0))
        mover.controlled = False
        with self.assertRaisesRegex(ValueError, "Invalid combat movement path"):
            fight.server_move(
                mover.id,
                [(-37, -29, 0), (-37, -28, 0), (-36, -28, 0)],
            )
        self.assertEqual((mover.position, mover.mp), ((-37, -30, 0), 6))

    def test_known_radius_legacy_fallback_checks_bodies_and_unknown_points_stay_unknown(
        self,
    ):
        from wakfu_server.combat.combat_qi_movement import movement_blocked_cells

        walkable = {(x, y, 0) for x in range(-3, 6) for y in range(-2, 3)}
        large = Actor(10, 0, (0, 0, 0), 40, 6, 3, 10, 10)
        point = Actor(20, 1, (3, 0, 0), 20, 0, 0, 1, 10)
        large.physical_radius, point.physical_radius = 1, 0
        fight = Fight(
            904,
            [large, point],
            walkable,
            {0: {large.position}, 1: {point.position}},
        )
        self.assertEqual(
            movement_blocked_cells(fight, large, [(1, 0, 0), (2, 0, 0)]),
            {(2, 0, 0)},
        )

        point.position = (0, 0, 0)
        large.position = (2, 0, 0)
        point.physical_radius, large.physical_radius = 0, 1
        point_first = Fight(
            905,
            [point, large],
            walkable,
            {0: {large.position}, 1: {point.position}},
        )
        self.assertEqual(
            movement_blocked_cells(point_first, point, [(1, 0, 0)]),
            {(1, 0, 0)},
        )

        # A walkable anchor cannot let a known large body hang outside the
        # serialized native terrain rectangle.
        edge = Actor(30, 0, (0, 0, 0), 40, 6, 3, 10, 10)
        other = Actor(40, 1, (4, 0, 0), 20, 0, 0, 1, 10)
        edge.physical_radius, other.physical_radius = 1, 0
        narrow = Fight(
            906,
            [edge, other],
            {(0, 0, 0), (1, 0, 0), (4, 0, 0)},
            {0: {edge.position}, 1: {other.position}},
        )
        self.assertEqual(movement_blocked_cells(narrow, edge, [(1, 0, 0)]), {(1, 0, 0)})

        first = Actor(50, 0, (0, 0, 0), 40, 6, 3, 10, 10)
        second = Actor(60, 1, (1, 0, 0), 20, 0, 0, 1, 10)
        unknown = Fight(
            907,
            [first, second],
            walkable,
            {0: {first.position}, 1: {second.position}},
        )
        self.assertIsNone(movement_blocked_cells(unknown, first, [(1, 0, 0)]))


if __name__ == "__main__":
    unittest.main()
