"""Duel terrain keeps player positions while using compact native geometry."""
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from wakfu_server.combat_terrain import local_arena


def grid(size):
    cells = [(x, y, 0) for x in range(size) for y in range(size)]
    known = set(cells)
    edges = [
        (cell, other)
        for cell in cells
        for other in (
            (cell[0] + 1, cell[1], 0),
            (cell[0] - 1, cell[1], 0),
            (cell[0], cell[1] + 1, 0),
            (cell[0], cell[1] - 1, 0),
        )
        if other in known
    ]
    return dict(map_id=777, cells=cells, edges=edges)


class FriendlyDuelCompactArenaTests(unittest.TestCase):
    def select(self, size, origin, target):
        # Exercise real selection and placement; isolate published surface and
        # wire serialization boundaries, which have their own integration tests.
        with ExitStack() as stack:
            prefix = "wakfu_server.combat_terrain."
            stack.enter_context(
                patch(prefix + "published_geometry", return_value=grid(size))
            )
            stack.enter_context(patch(prefix + "native_qi_surfaces", return_value={}))
            stack.enter_context(
                patch(prefix + "native_surface_indices", return_value={})
            )
            stack.enter_context(
                patch(prefix + "native_qi_surface_provenance", return_value={})
            )
            stack.enter_context(patch(prefix + "arena", return_value={}))
            stack.enter_context(
                patch.dict("os.environ", {"WAKFU_COMBAT_ARENA_RADIUS": "89"})
            )
            return local_arena(
                777,
                1,
                origin,
                [target],
                relocate_monsters=False,
                compact=True,
                minimum_dimensions=(30, 30),
                variation_seed=42,
            )

    def test_nearby_duel_has_compact_arena_and_original_placements(self):
        origin, target = (20, 20, 0), (23, 20, 0)
        result = self.select(45, origin, target)
        self.assertGreaterEqual(len(result["validated_cells"]), 900)
        self.assertLessEqual(len(result["validated_cells"]), 2500)
        self.assertIn(origin, result["placement_cells"][0])
        self.assertIn(target, result["placement_cells"][1])
        self.assertEqual(result["participant_positions"], [(target, target)])
        self.assertTrue(result["native_border_cells"])

    def test_separated_duel_expands_without_moving_either_player(self):
        origin, target = (5, 5, 0), (30, 25, 0)
        result = self.select(40, origin, target)
        self.assertIn(origin, result["placement_cells"][0])
        self.assertIn(target, result["placement_cells"][1])
        self.assertEqual(result["participant_positions"], [(target, target)])
        self.assertLessEqual(len(result["validated_cells"]), 2500)

    def test_adjacent_duelists_can_place_in_distant_distributed_regions(self):
        origin, target = (20, 20, 0), (21, 20, 0)
        result = self.select(45, origin, target)
        zones = result["placement_cells"]
        centroids = [
            tuple(sum(c[axis] for c in zones[t]) / len(zones[t]) for axis in (0, 1))
            for t in (0, 1)
        ]
        self.assertGreater(sum(abs(a - b) for a, b in zip(*centroids)), 12)
        for team in (0, 1):
            self.assertGreater(
                max(c[0] for c in zones[team]) - min(c[0] for c in zones[team]), 10
            )
            self.assertGreater(
                max(c[1] for c in zones[team]) - min(c[1] for c in zones[team]), 10
            )

    def test_pve_initial_opponents_spread_on_native_opposing_side(self):
        from wakfu_server.combat_arena_selection import compact_encounter

        origin = (10, 10, 0)
        originals = [(11, 10, 0), (10, 11, 0), (11, 11, 0)]
        result = compact_encounter(
            grid(30),
            origin,
            originals,
            minimum_cells=900,
            minimum_dimensions=(30, 30),
            spread_opponents=True,
        )
        destinations = [
            destination for _, destination in result["participant_positions"]
        ]
        self.assertTrue(all(cell in result["cells"] for cell in destinations))
        self.assertTrue(
            all(
                abs(c[0] - origin[0]) + abs(c[1] - origin[1]) > 15 for c in destinations
            )
        )
        self.assertGreater(
            max(
                abs(a[0] - b[0]) + abs(a[1] - b[1])
                for a in destinations
                for b in destinations
            ),
            15,
        )

    def test_adjacent_duelists_start_at_opposite_native_interior_positions(self):
        from wakfu_server.combat_placement_cells import opposing_starts

        result = self.select(45, (20, 20, 0), (21, 20, 0))
        starts = opposing_starts(
            result["validated_cells"],
            result["valid_edges"],
            result["placement_cells"],
            avoid_cells=result["native_border_cells"],
        )
        self.assertGreater(sum(abs(a - b) for a, b in zip(starts[0], starts[1])), 30)
        for team in (0, 1):
            self.assertIn(starts[team], result["placement_cells"][team])
            self.assertNotIn(starts[team], result["native_border_cells"])

    def test_budget_overflow_rejects_instead_of_relocating_player(self):
        with self.assertRaisesRegex(ValueError, "preserve participant positions"):
            self.select(65, (1, 1, 0), (60, 60, 0))


if __name__ == "__main__":
    unittest.main()
