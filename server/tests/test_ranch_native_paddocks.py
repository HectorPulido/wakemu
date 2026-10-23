"""Original JVM enclosed/open fence fixtures and owned-sector projection."""
import json
from pathlib import Path
import unittest

from wakfu_server import ranch_native_paddocks as paddocks
from wakfu_server import ranch_native_geometry as geometry


class RanchNativePaddockTests(unittest.TestCase):
    def test_original_closed_and_open_enclosures(self):
        fixture = json.loads(
            Path(__file__)
            .with_name("fixtures")
            .joinpath("ranch/native_paddock_oracle.json")
            .read_text()
        )
        plane = {(x, y) for x in range(18) for y in range(18)}
        perimeter = {
            (x, y)
            for x in range(4, 9)
            for y in range(4, 9)
            if x in (4, 8) or y in (4, 8)
        }
        for case in fixture:
            walls = perimeter if case["closed"] else perimeter - {(6, 4)}
            result = paddocks._regions(plane, walls)
            actual = sorted(
                [
                    dict(
                        interior=[list(p) for p in sorted(inside)],
                        boundary=[list(p) for p in sorted(edge)],
                    )
                    for inside, edge in result
                ],
                key=lambda row: row["interior"],
            )
            self.assertEqual(case["regions"], actual)

    def test_diagonal_escape_is_open_and_two_enclosures_stay_distinct(self):
        plane = {(x, y) for x in range(18) for y in range(18)}
        perimeter = {
            (x, y)
            for x in range(4, 9)
            for y in range(4, 9)
            if x in (4, 8) or y in (4, 8)
        }
        self.assertEqual([], paddocks._regions(plane, perimeter - {(4, 4)}))
        second = {(x + 7, y) for x, y in perimeter}
        self.assertEqual(2, len(paddocks._regions(plane, perimeter | second)))

    def test_public_owned_snapshot_has_no_fabricated_uid_and_preserves_input(self):
        sector_id, chunks = next(iter(geometry.sector_chunks(1).items()))
        cx, cy = next(iter(chunks))
        rows = []
        for x in range(4, 9):
            for y in range(4, 9):
                if x not in (4, 8) and y not in (4, 8):
                    continue
                rows.append(
                    dict(
                        uid=len(rows) + 1,
                        building_ref=6,
                        mode_id=1,
                        view_kind=1,
                        view_value=255,
                        x=cx * 18 + x,
                        y=cy * 18 + y,
                        sector_id=sector_id,
                    )
                )
        before = [dict(row) for row in rows]
        regions = paddocks.enclosed_regions(1, sector_id, rows)
        self.assertEqual(1, len(regions))
        self.assertEqual(
            {"sector_id", "group", "interior", "boundary"}, set(regions[0])
        )
        self.assertEqual(
            (sector_id, 1, 9),
            (regions[0]["sector_id"], regions[0]["group"], len(regions[0]["interior"])),
        )
        self.assertEqual(before, rows)
        with self.assertRaises(ValueError):
            paddocks.enclosed_regions(1, sector_id, [rows[0], rows[0]])


if __name__ == "__main__":
    unittest.main()
