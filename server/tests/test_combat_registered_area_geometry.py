"""Actual Qq registration geometry, separate from effect target membership."""
import unittest
import json
from pathlib import Path

from wakfu_server.combat_effect_area_geometry import registered_area_cells


class RegisteredAreaGeometryTests(unittest.TestCase):
    def test_registered_cross_matches_actual_native_qq_cache(self):
        path = Path(__file__).resolve().parents[2] / (
            "docs/reports/combat-inventory/native-registered-cross-oracle-20261007.json"
        )
        oracle = json.loads(path.read_text())
        self.assertEqual(len(oracle["cases"]), 288)
        for row in oracle["cases"]:
            with self.subTest(
                description=row["description"],
                direction=row["direction"],
                center=row["center"],
                reference=row["reference"],
            ):
                definition = dict(
                    native_shape_class="anw",
                    native_shape_description=row["description"],
                )
                self.assertEqual(
                    registered_area_cells(
                        definition,
                        tuple(row["center"]),
                        row["direction"],
                        reference=tuple(row["reference"]),
                    ),
                    tuple(tuple(cell) for cell in row["cells"]),
                )

    def point_shape(self):
        return dict(
            native_shape_class="anE",
            native_shape_description="forme à base de points",
            native_area_points=[[1, 0], [0, 1]],
        )

    def test_actual_owner_reference_overrides_coincident_facing(self):
        # ProbeNativeRegisteredAreaGeometry executes this exact Qq.bcT case.
        self.assertEqual(
            registered_area_cells(
                self.point_shape(), (5, 2, 9), 7, reference=(0, 0, 0)
            ),
            ((5, 3), (6, 2)),
        )

    def test_null_owner_keeps_actual_coincident_facing(self):
        self.assertEqual(
            registered_area_cells(self.point_shape(), (5, 2, 9), 7), ((5, 1), (6, 2))
        )

    def test_installed_point_metadata_is_present_and_consumable(self):
        from wakfu_server.combat_effect_area import native_effect_areas

        definitions = native_effect_areas()
        points = [
            row
            for row in definitions.values()
            if row["native_shape_class"] in ("anE", "anJ")
        ]
        self.assertEqual(len(points), 95)
        for row in points:
            with self.subTest(reference=row["reference"]):
                self.assertIn("native_area_points", row)
                for direction in range(8):
                    cells = registered_area_cells(
                        row, (2, 3, 9), direction, reference=(2, 3, -2)
                    )
                    self.assertIsInstance(cells, tuple)
