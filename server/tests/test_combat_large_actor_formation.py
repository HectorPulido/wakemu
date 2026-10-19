"""Initial formation must account for native actor footprints."""
import unittest

from wakfu_server.combat_arena_selection import compact_encounter


def grid(width, height):
    cells = {(x, y, 0) for x in range(width) for y in range(height)}
    edges = {
        (cell, (cell[0] + dx, cell[1] + dy, 0))
        for cell in cells
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if (cell[0] + dx, cell[1] + dy, 0) in cells
    }
    return {"map_id": 778, "cells": cells, "edges": edges}


def footprint(position, radius):
    x, y, _ = position
    return {
        (x + dx, y + dy)
        for dx in range(-radius, radius + 1)
        for dy in range(-radius, radius + 1)
    }


class LargeActorFormationTests(unittest.TestCase):
    def test_radius_one_enemies_and_player_get_disjoint_native_footprints(self):
        terrain = grid(17, 17)
        player = (8, 8, 0)
        originals = [(1, 1, 0), (15, 15, 0), (1, 15, 0)]
        radii = [0, 1, 1]

        result = compact_encounter(
            terrain,
            player,
            originals,
            minimum_cells=225,
            minimum_dimensions=(15, 15),
            spread_opponents=True,
            player_radius=1,
            member_radii=radii,
        )

        positions = [destination for _, destination in result["participant_positions"]]
        actor_footprints = [footprint(player, 1)] + [
            footprint(position, radius) for position, radius in zip(positions, radii)
        ]
        self.assertEqual(len(positions), len(originals))
        for index, cells in enumerate(actor_footprints):
            self.assertTrue(cells <= {(x, y) for x, y, _ in result["cells"]})
            for other in actor_footprints[index + 1 :]:
                self.assertTrue(cells.isdisjoint(other))
        self.assertEqual(
            [source for source, _ in result["participant_positions"]], originals
        )

    def test_tight_terrain_fails_closed_when_two_large_footprints_cannot_fit(self):
        terrain = grid(5, 5)
        with self.assertRaises(ValueError):
            compact_encounter(
                terrain,
                (2, 2, 0),
                [(0, 0, 0)],
                minimum_cells=25,
                minimum_dimensions=(5, 5),
                spread_opponents=True,
                player_radius=1,
                member_radii=[1],
            )

    def test_uncropped_map_cells_are_not_used_as_encounter_terrain(self):
        from unittest.mock import patch
        import wakfu_server.combat_terrain as terrain_module

        full = grid(20, 20)
        crop = {(x, y, 0) for x in range(2, 18) for y in range(2, 18)}
        with patch.object(
            terrain_module, "published_geometry", return_value=full
        ), patch.object(
            terrain_module, "native_qi_surfaces", return_value=()
        ), patch.object(
            terrain_module, "native_qi_surface_provenance", return_value=None
        ), patch.object(
            terrain_module,
            "native_surface_indices",
            side_effect=lambda _surfaces, cells: {cell[:2]: 0 for cell in cells},
        ):
            result = terrain_module.local_arena(
                778,
                1,
                (9, 9, 0),
                (12, 12, 0),
                relocate_monsters=True,
                compact=True,
                allowed_cells=crop,
                minimum_dimensions=(15, 15),
                automatic_cell_budget=225,
                member_radii=[1],
                player_radius=1,
            )

        self.assertTrue(set(result["validated_cells"]) <= crop)
        player = (9, 9, 0)
        _, member = result["participant_positions"][0]
        occupied = footprint(player, 1) | footprint(member, 1)
        self.assertTrue(footprint(player, 1).isdisjoint(footprint(member, 1)))
        borders = {cell[:2] for cell in result["native_border_cells"]}
        self.assertTrue(occupied.isdisjoint(borders))
        for team, center in ((0, player), (1, member)):
            optional = {cell[:2] for cell in result["placement_cells"][team] - {center}}
            self.assertTrue(
                optional.isdisjoint(occupied),
                "Optional placement slot overlaps an ordinary actor footprint",
            )

    def test_mismatched_radius_roster_is_rejected(self):
        with self.assertRaises(ValueError):
            compact_encounter(
                grid(9, 9),
                (4, 4, 0),
                [(1, 1, 0)],
                minimum_cells=81,
                minimum_dimensions=(9, 9),
                member_radii=[],
            )


class LargeActorPlacementTests(unittest.TestCase):
    @staticmethod
    def fight(*, player_position=(0, 0, 0), boss_position=(4, 4, 0), walkable=None):
        from wakfu_server.combat_state import Actor, Fight

        walkable = set(walkable or {(x, y, 0) for x in range(8) for y in range(8)})
        player = Actor(1, 0, player_position, 60, 6, 3, 10, 1, 7, True)
        boss = Actor(-2, 1, boss_position, 30, 4, 2, 0, 1)
        boss.physical_radius = 1
        player_cells = {
            cell
            for cell in (player_position, (4, 3, 0), (6, 4, 0), (0, 0, 0), (3, 3, 0))
            if cell in walkable
        }
        placement = {
            0: player_cells,
            1: {boss_position},
        }
        return Fight(5, [player, boss], walkable, placement), player

    def test_radius_zero_player_cannot_place_inside_radius_one_boss_footprint(self):
        fight, player = self.fight()
        player.physical_radius = 0

        with self.assertRaisesRegex(ValueError, "occupied"):
            fight.place(7, player.id, (4, 3, 0))

    def test_radius_zero_player_can_place_adjacent_to_large_boss(self):
        fight, player = self.fight()
        player.physical_radius = 0

        fight.place(7, player.id, (6, 4, 0))

        self.assertEqual(player.position, (6, 4, 0))

    def test_large_controlled_footprint_outside_walkable_terrain_is_rejected(self):
        walkable = {(x, y, 0) for x in range(1, 8) for y in range(1, 8)}
        fight, player = self.fight(
            player_position=(2, 2, 0), boss_position=(7, 7, 0), walkable=walkable
        )
        player.physical_radius = 1
        # A large actor may be restored at its native position; a new placement
        # must still prove every cell in its inclusive footprint is walkable.
        fight.placement[0].add((1, 1, 0))

        with self.assertRaisesRegex(ValueError, "footprint"):
            fight.place(7, player.id, (1, 1, 0))

    def test_large_controlled_footprint_cannot_cross_native_border(self):
        fight, player = self.fight()
        player.physical_radius = 1
        fight.native_border_cells = {(2, 3, 0)}

        with self.assertRaisesRegex(ValueError, "border"):
            fight.place(7, player.id, (3, 3, 0))


if __name__ == "__main__":
    unittest.main()
