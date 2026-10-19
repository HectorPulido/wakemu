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
    @staticmethod
    def _reachable(edges, start, blocked=()):
        outgoing = {}
        for source, target in edges:
            outgoing.setdefault(source, set()).add(target)
        blocked = set(blocked)
        found = {start}
        pending = [start]
        while pending:
            for target in outgoing.get(pending.pop(), ()):
                if target not in blocked and target not in found:
                    found.add(target)
                    pending.append(target)
        return found

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

    def test_adjacent_duelists_keep_cohesive_native_formations_near_seeds(self):
        origin, target = (20, 20, 0), (21, 20, 0)
        result = self.select(45, origin, target)
        zones = result["placement_cells"]
        cells = result["validated_cells"]
        edges = result["valid_edges"]
        borders = result["native_border_cells"]

        self.assertEqual(len(zones[0]), 12)
        self.assertEqual(len(zones[1]), 12)
        self.assertIn(origin, zones[0])
        self.assertIn(target, zones[1])
        self.assertFalse(zones[0] & zones[1])
        self.assertFalse((zones[0] | zones[1]) & borders)
        self.assertTrue((zones[0] | zones[1]) <= cells)
        for team, seed in ((0, origin), (1, target)):
            forward = self._reachable(edges, seed, borders)
            reverse = self._reachable(
                [(destination, source) for source, destination in edges], seed, borders
            )
            self.assertTrue(zones[team] <= forward)
            self.assertTrue(zones[team] <= reverse)
            self.assertLessEqual(
                max(self._distance(edges, seed, cell, borders) for cell in zones[team]),
                3,
            )

    @staticmethod
    def _distance(edges, start, destination, blocked=()):
        outgoing = {}
        for source, target in edges:
            outgoing.setdefault(source, set()).add(target)
        blocked = set(blocked)
        distances = {start: 0}
        pending = [start]
        while pending:
            current = pending.pop(0)
            if current == destination:
                return distances[current]
            for neighbor in outgoing.get(current, ()):
                if neighbor not in blocked and neighbor not in distances:
                    distances[neighbor] = distances[current] + 1
                    pending.append(neighbor)
        raise AssertionError("Formation cell has no native route from its seed")

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
        self.assertLessEqual(
            max(
                abs(a[0] - b[0]) + abs(a[1] - b[1])
                for a in destinations
                for b in destinations
            ),
            4,
        )
        forward = self._reachable(result["edges"], origin)
        reverse = self._reachable(
            [(destination, source) for source, destination in result["edges"]],
            origin,
        )
        self.assertTrue(set(destinations) <= forward)
        self.assertTrue(set(destinations) <= reverse)

    def test_adjacent_duelists_start_on_legal_mutually_reachable_interior_cells(self):
        from wakfu_server.combat.combat_placement_cells import opposing_starts

        origin, target = (20, 20, 0), (21, 20, 0)
        result = self.select(45, origin, target)
        zones = result["placement_cells"]
        edges = result["valid_edges"]
        borders = result["native_border_cells"]
        starts = opposing_starts(
            result["validated_cells"],
            edges,
            zones,
            avoid_cells=borders,
        )

        self.assertEqual(len(zones[0]), 12)
        self.assertEqual(len(zones[1]), 12)
        self.assertIn(origin, zones[0])
        self.assertIn(target, zones[1])
        self.assertIn(starts[0], zones[0])
        self.assertIn(starts[1], zones[1])
        self.assertFalse(set(starts.values()) & borders)
        forward = self._reachable(edges, starts[0], borders)
        reverse = self._reachable(
            [(destination, source) for source, destination in edges],
            starts[0],
            borders,
        )
        self.assertIn(starts[1], forward)
        self.assertIn(starts[1], reverse)

    def test_budget_overflow_rejects_instead_of_relocating_player(self):
        with self.assertRaisesRegex(ValueError, "preserve participant positions"):
            self.select(65, (1, 1, 0), (60, 60, 0))


if __name__ == "__main__":
    unittest.main()
