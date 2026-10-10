import unittest
from wakfu_server.combat_arena_selection import MAX_CELL_BUDGET, bounded_arena


def topology(cells, edges):
    return dict(map_id=777, cells=cells, edges=edges)


def pairs(path):
    return [(a, b) for a, b in zip(path, path[1:])] + [
        (b, a) for a, b in zip(path, path[1:])
    ]


class ArenaSelectionTests(unittest.TestCase):
    def test_native_staircase_keeps_heights_and_places_entire_group(self):
        path = [(0, 0, 0), (1, 0, 2), (2, 0, 4), (3, 0, 4)]
        result = bounded_arena(topology(path, pairs(path)), path[0], [path[2], path[3]])
        self.assertEqual(result["cells"], set(path))
        self.assertEqual(result["edges"], set(pairs(path)))
        self.assertEqual(result["placement"], {0: [path[0]], 1: [path[2], path[3]]})

    def test_disconnected_stacked_floor_does_not_hide_valid_lower_floor(self):
        lower = [(0, 0, 0), (1, 0, 0), (2, 0, 0)]
        upper = [(0, 0, 10), (1, 0, 10), (2, 0, 10)]
        result = bounded_arena(
            topology(lower + upper, pairs(lower) + pairs(upper)), lower[0], [lower[-1]]
        )
        self.assertEqual(result["cells"], set(lower))
        with self.assertRaises(ValueError):
            bounded_arena(
                topology(lower + upper, pairs(lower) + pairs(upper)),
                lower[0],
                [upper[-1]],
            )

    def test_reachable_ambiguous_bridge_cannot_connect_group_by_guessing_height(self):
        cells = [(0, 0, 0), (1, 0, 0), (1, 0, 2), (2, 0, 0), (0, 1, 0)]
        edges = [
            (cells[0], cells[1]),
            (cells[0], cells[2]),
            (cells[1], cells[3]),
            (cells[0], cells[4]),
        ]
        result = bounded_arena(topology(cells, edges), cells[0], [cells[4]])
        self.assertEqual(result["blocked_ambiguous"], {(1, 0)})
        self.assertEqual(result["cells"], {cells[0], cells[4]})
        with self.assertRaises(ValueError):
            bounded_arena(topology(cells, edges), cells[0], [cells[3]])

    def test_crop_requires_path_within_bounds_and_preserves_directed_edges(self):
        path = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)]
        data = topology(path, [(a, b) for a, b in zip(path, path[1:])])
        result = bounded_arena(data, path[0], [path[2]], radius=2)
        self.assertEqual(result["bounds"], (0, 0, 2, 0))
        self.assertNotIn((path[1], path[0]), result["edges"])
        with self.assertRaises(ValueError):
            bounded_arena(data, path[0], [path[3]], radius=2)
        with self.assertRaises(ValueError):
            bounded_arena(data, path[-1], [path[0]])

    def test_malformed_coordinates_edges_roster_and_wire_radius_fail(self):
        cells = [(0, 0, 0), (1, 0, 0)]
        data = topology(cells, pairs(cells))
        for radius in (True, 0, 90):
            with self.assertRaises(ValueError):
                bounded_arena(data, cells[0], [cells[1]], radius)
        with self.assertRaises(ValueError):
            bounded_arena(data, cells[0], [cells[0]])
        with self.assertRaises(ValueError):
            bounded_arena(
                topology(cells, [(cells[0], (2, 0, 0))]), cells[0], [cells[1]]
            )
        with self.assertRaises(ValueError):
            bounded_arena(data, (0, 0, 40000), [cells[1]])


class CompactEncounterTests(unittest.TestCase):
    def test_all_remote_monsters_relocate_inside_mutually_reachable_compact_component(
        self,
    ):
        from wakfu_server.combat_arena_selection import compact_encounter, _reachable

        floor = [(x, 0, 0) for x in range(-20, 21)]
        platform = [(x, 0, 9) for x in range(20, 25)]
        result = compact_encounter(
            topology(floor + platform, pairs(floor) + pairs(platform)),
            (0, 0, 0),
            [(20, 0, 9), (24, 0, 9), (-20, 0, 0)],
        )
        positions = result["placement"][1]
        self.assertEqual(len(set(positions)), 3)
        self.assertTrue(all(p[2] == 0 for p in positions))
        self.assertLessEqual(len(result["cells"]), MAX_CELL_BUDGET)
        for position in positions:
            self.assertIn(
                (0, 0, 0), _reachable(position, result["cells"], result["edges"])
            )

    def test_one_way_drop_is_not_valid_monster_destination(self):
        from wakfu_server.combat_arena_selection import compact_encounter

        path = [(0, 0, 0), (1, 0, 0), (2, 0, -5)]
        result = compact_encounter(
            topology(path, pairs(path[:2]) + [(path[1], path[2])]), path[0], [path[2]]
        )
        self.assertEqual(result["placement"][1], [path[1]])
        self.assertNotIn(path[2], result["cells"])

    def test_capacity_failure_never_invents_walkable_cells(self):
        from wakfu_server.combat_arena_selection import compact_encounter

        path = [(0, 0, 0), (1, 0, 0)]
        with self.assertRaisesRegex(ValueError, "capacity"):
            compact_encounter(
                topology(path, pairs(path)), path[0], [(50, 0, 0), (51, 0, 0)]
            )


class EncounterCellBudgetTests(unittest.TestCase):
    def grid(self, width, height):
        cells = {(x, y, 0) for x in range(width) for y in range(height)}
        edges = [
            (c, (c[0] + dx, c[1] + dy, 0))
            for c in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (c[0] + dx, c[1] + dy, 0) in cells
        ]
        return topology(cells, edges)

    def test_ten_by_twohundredfifty_is_not_limited_by_radius_or_side_length(self):
        from wakfu_server.combat_arena_selection import compact_encounter

        result = compact_encounter(
            self.grid(10, 250), (0, 0, 0), [(9, 249, 0)], cell_budget=MAX_CELL_BUDGET
        )
        self.assertEqual(len(result["cells"]), MAX_CELL_BUDGET)
        self.assertEqual(result["bounds"], (0, 0, 9, 249))
        self.assertEqual(result["placement"][1], [(9, 249, 0)])

    def test_fifty_square_budget_and_oversized_grid_are_connected(self):
        from wakfu_server.combat_arena_selection import compact_encounter, _reachable

        for size in (50, 80):
            result = compact_encounter(
                self.grid(size, size),
                (0, 0, 0),
                [(size - 1, size - 1, 0)],
                cell_budget=MAX_CELL_BUDGET,
            )
            self.assertEqual(len(result["cells"]), MAX_CELL_BUDGET)
            self.assertEqual(
                _reachable((0, 0, 0), result["cells"], result["edges"]), result["cells"]
            )
            enemy = result["placement"][1][0]
            self.assertIn(enemy, result["cells"])
            self.assertIn(
                (0, 0, 0), _reachable(enemy, result["cells"], result["edges"])
            )
            self.assertLessEqual(
                (result["bounds"][2] + 1) * (result["bounds"][3] + 1), 32767
            )

    def test_sparse_l_shape_counts_blocked_rectangle_holes_in_map_budget(self):
        from wakfu_server.combat_arena_selection import compact_encounter, _reachable

        path = [(x, 0, 0) for x in range(150)] + [(149, y, 0) for y in range(1, 150)]
        result = compact_encounter(topology(path, pairs(path)), path[0], [path[-1]])
        x0, y0, x1, y1 = result["bounds"]
        self.assertLessEqual((x1 - x0 + 1) * (y1 - y0 + 1), MAX_CELL_BUDGET)
        self.assertLess(len(result["cells"]), MAX_CELL_BUDGET)
        self.assertNotIn(path[-1], result["cells"])
        enemy = result["placement"][1][0]
        self.assertIn(enemy, result["cells"])
        self.assertIn(path[0], _reachable(enemy, result["cells"], result["edges"]))


class AutomaticArenaSizeTests(unittest.TestCase):
    grid = EncounterCellBudgetTests.grid

    def test_feasible_enemy_origin_is_preserved_even_when_it_expands_the_arena(self):
        from wakfu_server.combat_arena_selection import compact_encounter

        result = compact_encounter(self.grid(80, 80), (40, 40, 0), [(79, 79, 0)])
        self.assertEqual(result["placement"][1], [(79, 79, 0)])
        self.assertIn((79, 79, 0), result["cells"])
        x0, y0, x1, y1 = result["bounds"]
        self.assertLessEqual((x1 - x0 + 1) * (y1 - y0 + 1), MAX_CELL_BUDGET)

    def test_large_roster_expands_beyond_minimum(self):
        from wakfu_server.combat_arena_selection import compact_encounter

        result = compact_encounter(
            self.grid(20, 20), (0, 0, 0), [(100 + n, 100, 0) for n in range(40)]
        )
        self.assertGreaterEqual(len(result["cells"]), 64)
        self.assertEqual(len(set(result["placement"][1])), 40)

    def test_small_native_component_is_usable_below_minimum(self):
        from wakfu_server.combat_arena_selection import compact_encounter

        result = compact_encounter(self.grid(3, 3), (0, 0, 0), [(2, 2, 0)])
        self.assertEqual(len(result["cells"]), 9)
