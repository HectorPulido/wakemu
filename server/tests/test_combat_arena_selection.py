import unittest
from wakfu_server.combat_arena_selection import bounded_arena


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
