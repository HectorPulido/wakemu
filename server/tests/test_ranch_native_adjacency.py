"""Original JVM fBL/fBu oracle, including complete 8-neighbor mask domains."""
import json
from pathlib import Path
import unittest

from wakfu_server import ranch_native_adjacency as adjacency
from wakfu_server.haven_ranch_building_catalog import definition, mode, view


class RanchNativeAdjacencyTests(unittest.TestCase):
    def test_all_original_neighbor_masks_and_selected_native_views(self):
        oracle = json.loads(
            Path(__file__)
            .with_name("fixtures")
            .joinpath("ranch/native_adjacency_oracle.json")
            .read_text()
        )
        self.assertEqual({"6:1", "8:1"}, set(oracle))
        for identity, cases in oracle.items():
            reference, mode_id = map(int, identity.split(":"))
            building = definition(reference)
            keys = [row["epL"] for row in mode(building, mode_id)["epQ"]]
            self.assertEqual(256, len(cases))
            for observed, (expected_key, expected_view) in enumerate(cases):
                with self.subTest(reference=reference, observed=observed):
                    selected = adjacency.select_adjacent_key(observed, keys)
                    self.assertEqual(expected_key, selected)
                    if selected is not None:
                        self.assertEqual(
                            expected_view, view(building, mode_id, 1, selected)["eki"]
                        )

    def test_superset_population_and_numeric_tie_contract(self):
        self.assertEqual(85, adjacency.select_adjacent_key(0, (255, 85, 170)))
        self.assertEqual(87, adjacency.select_adjacent_key(2, (255, 87, 119)))
        self.assertEqual(3, adjacency.select_adjacent_key(1, (5, 3)))
        self.assertIsNone(adjacency.select_adjacent_key(128, (3, 7)))
        for invalid in (-1, 256, True):
            with self.assertRaises(ValueError):
                adjacency.select_adjacent_key(invalid, (255,))

    @staticmethod
    def row(uid, reference, x, y):
        return dict(
            uid=uid,
            building_ref=reference,
            mode_id=1,
            view_kind=1,
            view_value=255,
            x=x,
            y=y,
            sector_id=2,
            revision=8,
            owned_payload={"unchanged": True},
        )

    def test_insert_remove_move_and_cross_reference_group(self):
        anchor = self.row(1, 6, 0, -36)
        east = self.row(2, 8, 1, -36)
        isolated = adjacency.recompute_adjacent_building_views(1, [anchor])
        inserted = adjacency.recompute_adjacent_building_views(1, [anchor, east])
        removed = adjacency.recompute_adjacent_building_views(1, inserted[:1])
        moved = adjacency.recompute_adjacent_building_views(
            1, [anchor, {**east, "x": 4}]
        )
        self.assertEqual([85], [row["view_value"] for row in isolated])
        self.assertEqual([87, 119], [row["view_value"] for row in inserted])
        self.assertEqual([85], [row["view_value"] for row in removed])
        self.assertEqual([85, 119], [row["view_value"] for row in moved])
        for before, after in zip([anchor, east], inserted):
            self.assertEqual(
                {
                    k: v
                    for k, v in before.items()
                    if k not in {"view_kind", "view_value"}
                },
                {
                    k: v
                    for k, v in after.items()
                    if k not in {"view_kind", "view_value"}
                },
            )
        self.assertEqual(255, anchor["view_value"])
        self.assertEqual(255, east["view_value"])

    def test_other_groups_stay_unchanged_and_overlap_is_rejected(self):
        row = dict(
            uid=9,
            building_ref=16,
            mode_id=1,
            view_kind=0,
            view_value=1,
            x=0,
            y=-36,
            sector_id=2,
        )
        self.assertEqual([row], adjacency.recompute_adjacent_building_views(1, [row]))
        with self.assertRaises(ValueError):
            adjacency.recompute_adjacent_building_views(
                1, [self.row(1, 6, 0, -36), self.row(2, 8, 0, -36)]
            )


if __name__ == "__main__":
    unittest.main()
