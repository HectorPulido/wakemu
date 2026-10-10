import unittest
from wakfu_server.combat_forced_footprint import forced_footprint_step
from wakfu_server.combat_sn_path import NativePhysicalSurface


def surface(z=0):
    return NativePhysicalSurface(z, 0, 0, 0, 0, False)


class NativeForcedFootprintTests(unittest.TestCase):
    def evaluate(self, *, radius=1, blocked=(), columns=None, obstruction=None):
        visits = []
        result = forced_footprint_step(
            (4, 4, 0),
            (5, 4),
            radius=radius,
            height=6,
            physical_column=lambda x, y: (columns or {}).get((x, y), (surface(),)),
            terrain_valid=lambda x, y: (x, y) not in blocked,
            obstruction=obstruction
            or (lambda cell: (visits.append(cell) or False, None)),
        )
        return result, visits

    def test_original_square_order_repeats_center_after_all_offsets(self):
        result, visits = self.evaluate()
        self.assertEqual(result.destination, (5, 4, 0))
        self.assertFalse(result.collision)
        self.assertEqual(
            visits, [(x, y, 0) for x in range(4, 7) for y in range(3, 6)] + [(5, 4, 0)]
        )

    def test_offset_surface_compares_source_center_not_source_offset(self):
        result, _ = self.evaluate(columns={(4, 3): (surface(4),)})
        self.assertEqual(result.destination, (5, 4, 0))
        result, _ = self.evaluate(columns={(4, 3): (surface(5),)})
        self.assertIsNone(result.destination)
        self.assertTrue(result.collision)

    def test_footprint_edge_blocks_even_when_center_is_clear(self):
        result, visits = self.evaluate(radius=2, blocked={(7, 6)})
        self.assertIsNone(result.destination)
        self.assertTrue(result.collision)
        self.assertNotIn((7, 6, 0), visits)
        self.assertEqual(len(visits), 24)

    def test_first_actual_collision_preserves_collider_and_stops_iteration(self):
        calls = []

        def obstruction(cell):
            calls.append(cell)
            return (True, 88) if cell[:2] == (4, 4) else (False, None)

        result, _ = self.evaluate(obstruction=obstruction)
        self.assertIsNone(result.destination)
        self.assertTrue(result.collision)
        self.assertEqual(result.collider_id, 88)
        self.assertEqual(calls, [(4, 3, 0), (4, 4, 0)])

    def test_absent_native_chunk_aborts_without_collision(self):
        result, visits = self.evaluate(columns={(4, 3): None})
        self.assertIsNone(result.destination)
        self.assertFalse(result.collision)
        self.assertEqual(visits, [])
