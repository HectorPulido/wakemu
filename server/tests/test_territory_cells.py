import json
import unittest

from wakfu_server.paths import DATA_ROOT
from wakfu_server.territory_cells import GRID_SIZE, _cells, region_at
from wakfu_server import native_catalog


class TerritoryCellTests(unittest.TestCase):
    def test_export_covers_every_native_region_and_only_nonoverlapping_cells(self):
        catalog = json.loads(
            native_catalog.read_text(DATA_ROOT / "ecology-regions.json")
        )
        mapped = _cells()
        expected = {
            row["map_id"]: {region["region_id"] for region in row["regions"]}
            for row in catalog
            if row["regions"]
        }
        self.assertEqual(set(mapped), set(expected))
        for map_id, region_ids in expected.items():
            exported = {
                region
                for region in region_ids
                if any(owner == region for owner in mapped[map_id].values())
            }
            self.assertEqual(exported, region_ids, map_id)
            self.assertTrue(mapped[map_id])

    def test_native_lookup_uses_floor_grid_for_negative_coordinates(self):
        self.assertEqual(GRID_SIZE, 18)
        # Native `Ve.qb/qc` floor each coordinate divided by 18. In particular,
        # -19 belongs to grid -2 and -18 to grid -1 (Java truncation differs).
        native = _cells()[1134]
        self.assertEqual(region_at(1134, -19, -144), native[(-2, -8)])
        self.assertEqual(region_at(1134, -18, -144), native[(-1, -8)])
        self.assertEqual(region_at(1134, -36, -144), native[(-2, -8)])

    def test_nonplantable_position_in_same_territory_resolves_weather_region(self):
        # This is the native x/y territory boundary map, not the narrower set
        # of cells that can be planted on. Z does not participate in bMh.dV.
        from wakfu_server.planting_cells import cells as planting_cells

        candidates = [
            (x, y)
            for x in range(-36, -18)
            for y in range(-144, -126)
            if (x, y) not in planting_cells(1134)
        ]
        x, y = next((x, y) for x, y in candidates if region_at(1134, x, y) == 79201)
        self.assertEqual(region_at(1134, x, y), 79201)

    def test_unknown_or_malformed_position_never_gets_default_territory(self):
        for args in (
            (99999, 0, 0),
            (1134, 10000, 10000),
            (True, 0, 0),
            (1134, 0, False),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                region_at(*args)


if __name__ == "__main__":
    unittest.main()
