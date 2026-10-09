import unittest

from wakfu_server.combat_qi_surfaces import NativeQISurfaces
from wakfu_server.combat_qi_surface_selection import native_surface_indices
from wakfu_server.combat_qi_snapshot import NativeQISnapshot
from wakfu_server.combat_wire import arena, topology, decode_topology


class NativeSurfaceSelectionTests(unittest.TestCase):
    def surfaces(self, columns, extra_chunks=()):
        return NativeQISurfaces(
            {
                "schema": "native-QI-Vy-columns-v1",
                "map_id": 1134,
                "source_sha256": "a" * 64,
                "chunks": [
                    {"x": 0, "y": 0, "width": 2, "height": 2, "columns": columns},
                    *extra_chunks,
                ],
            },
            map_id=1134,
            source_sha256="a" * 64,
        )

    def test_selected_nonzero_surface_roundtrips_and_preserves_other_cells(self):
        surfaces = self.surfaces(
            [[0, 0, [[-4, -1], [19, 0]]], [1, 0, [[3, -7]]], [0, 1, [[8, -1]]]]
        )
        cells = [(0, 0, 19), (1, 0, 3), (0, 1, 8)]
        indices = native_surface_indices(surfaces, cells)
        encoded = arena(
            1134,
            1,
            cells,
            {0: cells[0], 1: cells[1]},
            surface_indices=indices,
            obstacle_values=[(9, 0)],
        )
        decoded = decode_topology(topology(encoded))
        self.assertEqual(decoded, encoded)
        self.assertEqual(decoded["cell_masks"], [1, 0, 0, 256])
        self.assertEqual(decoded["cell_flags"], bytes([0, 1, 255, 255]))
        self.assertEqual(decoded["team_values"], [(9, 0)])
        qi = NativeQISnapshot(decoded)
        self.assertTrue(surfaces.j(qi, 0, 0, 19))
        self.assertIsNone(surfaces.i(qi, 0, 0, -4))
        self.assertTrue(surfaces.j(qi, 1, 0, 3))
        self.assertFalse(surfaces.j(qi, 0, 1, 8))

    def test_missing_ambiguous_and_unencodable_surface_are_rejected(self):
        cases = [
            ([], [(0, 0, 0)]),
            ([[0, 0, [[0, 0], [0, 1]]]], [(0, 0, 0)]),
            ([[0, 0, [[i, 0] for i in range(65)]]], [(0, 0, 64)]),
            ([[0, 0, [[0, 0]]]], [(3, 3, 0)]),
        ]
        for columns, cells in cases:
            with self.subTest(columns=len(columns), cells=cells):
                with self.assertRaises(ValueError):
                    native_surface_indices(self.surfaces(columns), cells)

    def test_first_matching_empty_chunk_does_not_search_later_match(self):
        later = {"x": 0, "y": 0, "width": 1, "height": 1, "columns": [[0, 0, [[0, 0]]]]}
        with self.assertRaises(ValueError):
            native_surface_indices(self.surfaces([], [later]), [(0, 0, 0)])

    def test_capacity_boundary_and_invalid_coordinates(self):
        surfaces = self.surfaces([[0, 0, [[i, 0] for i in range(64)]]])
        self.assertEqual(native_surface_indices(surfaces, [(0, 0, 63)]), {(0, 0): 63})
        for cells in ([], [(False, 0, 0)], [(0, 0, 32768)], [(0, 0, 0), (0, 0, 1)]):
            with self.subTest(cells=cells):
                with self.assertRaises(ValueError):
                    native_surface_indices(surfaces, cells)

    def test_wire_requires_complete_strict_indices_when_explicit(self):
        cells = [(0, 0, 0), (1, 0, 0)]
        placement = {0: cells[0], 1: cells[1]}
        for indices in (
            {(0, 0): 0},
            {(0, 0): 0, (1, 0): False},
            {(0, 0): 0, (1, 0): 64},
            {(0, 0): 0, (1, 0): -1},
        ):
            with self.subTest(indices=indices):
                with self.assertRaises(ValueError):
                    arena(1134, 1, cells, placement, surface_indices=indices)


if __name__ == "__main__":
    unittest.main()
