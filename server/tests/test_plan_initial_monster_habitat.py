import unittest

from tools.plan_initial_monster_habitat import candidate


class InitialMonsterHabitatPlannerTests(unittest.TestCase):
    map_id = 527
    region_id = 75701
    reference = 6
    level = 4
    first = (-75, -68, 0)
    second = (-76, -68, 0)

    def geometry(self, *, cells=None, edges=None, map_id=None):
        return {
            "map_id": self.map_id if map_id is None else map_id,
            "cells": [self.first, self.second] if cells is None else cells,
            "edges": [(self.first, self.second), (self.second, self.first)]
            if edges is None
            else edges,
        }

    def locate(self, map_id, x, y, z):
        if map_id == self.map_id and (x, y, z) in (self.first, self.second):
            return {"region_id": self.region_id}
        return {"region_id": self.region_id + 1}

    def propose(self, **kwargs):
        geometry = kwargs.pop("geometry", self.geometry())
        return candidate(
            self.map_id,
            self.region_id,
            self.reference,
            self.level,
            geometry=geometry,
            locate=self.locate,
            **kwargs,
        )

    def test_accepts_native_adjacent_bidirectional_pair_deterministically(self):
        expected = {
            "map_id": self.map_id,
            "instance_id": 0,
            "region_id": self.region_id,
            "members": [
                {"reference": 6, "level": 4, "x": -76, "y": -68, "z": 0},
                {"reference": 6, "level": 4, "x": -75, "y": -68, "z": 0},
            ],
        }
        self.assertEqual(self.propose(), expected)

    def test_rejects_one_way_walking_edge(self):
        with self.assertRaisesRegex(ValueError, "bidirectional adjacent pair"):
            self.propose(geometry=self.geometry(edges=[(self.first, self.second)]))

    def test_rejects_pair_on_different_heights(self):
        upper = (self.second[0], self.second[1], self.second[2] + 1)
        geometry = self.geometry(
            cells=[self.first, upper],
            edges=[(self.first, upper), (upper, self.first)],
        )
        with self.assertRaisesRegex(ValueError, "bidirectional adjacent pair"):
            candidate(
                self.map_id,
                self.region_id,
                self.reference,
                self.level,
                geometry=geometry,
                locate=lambda *_: {"region_id": self.region_id},
            )

    def test_rejects_pair_spanning_native_regions(self):
        with self.assertRaisesRegex(ValueError, "bidirectional adjacent pair"):
            candidate(
                self.map_id,
                self.region_id,
                self.reference,
                self.level,
                geometry=self.geometry(),
                locate=lambda _map, x, _y, _z: {
                    "region_id": self.region_id
                    if x == self.first[0]
                    else self.region_id + 1
                },
            )

    def test_excluded_cells_cannot_be_selected(self):
        with self.assertRaisesRegex(ValueError, "bidirectional adjacent pair"):
            self.propose(excluded=[self.first])

    def test_minimum_component_rejects_two_cell_island(self):
        with self.assertRaisesRegex(ValueError, "bidirectional adjacent pair"):
            self.propose(minimum_component=3)

    def test_minimum_component_accepts_pair_inside_three_cell_component(self):
        a, b, c = (-70, -68, 0), (-69, -68, 0), (-68, -68, 0)
        geometry = self.geometry(
            cells=[a, b, c],
            edges=[(a, b), (b, a), (b, c), (c, b)],
        )
        plan = candidate(
            self.map_id,
            self.region_id,
            self.reference,
            self.level,
            geometry=geometry,
            locate=lambda *_: {"region_id": self.region_id},
            minimum_component=3,
        )
        self.assertEqual(
            [(row["x"], row["y"], row["z"]) for row in plan["members"]],
            [a, b],
        )

    def test_rejects_reference_not_native_to_habitat(self):
        # Reference 2601 is valid at level 4, but belongs to another family.
        with self.assertRaisesRegex(ValueError, "family is not native"):
            candidate(
                self.map_id,
                self.region_id,
                2601,
                4,
                geometry=self.geometry(),
                locate=self.locate,
            )

    def test_rejects_boolean_and_out_of_range_geometry_cells(self):
        invalid_cells = (
            (True, self.first[1], self.first[2]),
            (1 << 31, self.first[1], self.first[2]),
            (self.first[0], self.first[1], 1 << 15),
        )
        for invalid in invalid_cells:
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ValueError, "Invalid habitat cell coordinates"
            ):
                self.propose(geometry=self.geometry(cells=[invalid, self.second]))

    def test_rejects_invalid_edge_endpoint_and_excluded_cell(self):
        invalid = (self.first[0], self.first[1], -(1 << 15) - 1)
        malformed_edges = self.geometry(
            edges=[(self.first, invalid), (invalid, self.first)]
        )
        with self.assertRaisesRegex(ValueError, "Invalid habitat cell coordinates"):
            self.propose(geometry=malformed_edges)
        with self.assertRaisesRegex(ValueError, "Invalid habitat cell coordinates"):
            self.propose(excluded=[invalid])


if __name__ == "__main__":
    unittest.main()
