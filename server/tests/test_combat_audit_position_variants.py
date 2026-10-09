"""Placement search only uses existing same-height native cell corridors."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_class_position_variants import placement_pair


class NativePlacementVariantTests(unittest.TestCase):
    def test_requested_range_boundary_uses_existing_cells(self):
        cells = [(x, 0, 7) for x in range(7)]
        for distance in (1, 2, 3, 6):
            source, target = placement_pair(cells, distance, (0, 0, 7))
            self.assertEqual(source, (0, 0, 7))
            self.assertEqual(target, (distance, 0, 7))

    def test_missing_corridor_or_wrong_height_is_not_fabricated(self):
        for cells in (((0, 0, 7), (2, 0, 7)), ((0, 0, 7), (1, 0, 8), (2, 0, 7))):
            with self.assertRaisesRegex(ValueError, "actual same-height"):
                placement_pair(cells, 2, (0, 0, 7))
