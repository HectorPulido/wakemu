"""Native surfaces remain required regardless of regional family ownership."""
import unittest
from unittest.mock import patch

from wakfu_server.monster_habitat_cells import habitat_destination_allowed
from wakfu_server.monster_initial_population import REGIONS


class MonsterHabitatCellTests(unittest.TestCase):
    def test_reported_gobball_border_surfaces_allow_births_across_regions(self):
        parent = dict(x=-162, y=-125, z=-4)
        self.assertTrue(
            habitat_destination_allowed(527, 0, (-162, -125, -4), parent=parent)
        )
        self.assertTrue(
            habitat_destination_allowed(527, 0, (-163, -125, -4), parent=parent)
        )

    def test_unknown_maps_and_private_instances_keep_existing_reachability_policy(self):
        self.assertTrue(habitat_destination_allowed(527, 17, (-163, -125, -4)))
        self.assertTrue(habitat_destination_allowed(999999, 0, (1, 2, 3)))

    def test_known_outdoor_cell_requires_height_but_ignores_region_and_family(self):
        habitats = {
            (527, 7): {"monster_capacity": 50, "monster_families": [{"family_id": 68}]},
            (527, 8): {"monster_capacity": 50, "monster_families": [{"family_id": 68}]},
        }

        def surface(_map, x, _y, z):
            if z != -4:
                raise ValueError("Unknown native surface height")
            return {"region_id": 7 if x < 10 else 8}

        with patch.dict(REGIONS, habitats, clear=True), patch(
            "wakfu_server.planting_cells.surface", side_effect=surface
        ), patch(
            "wakfu_server.territory_cells.region_at",
            side_effect=lambda _map, x, _y: 7 if x < 10 else 8,
        ):
            parent = dict(x=1, y=2, z=-4)
            self.assertTrue(
                habitat_destination_allowed(
                    527, 0, (2, 2, -4), parent=parent, family_id=68
                )
            )
            self.assertFalse(
                habitat_destination_allowed(
                    527, 0, (2, 2, -3), parent=parent, family_id=68
                )
            )
            self.assertTrue(
                habitat_destination_allowed(
                    527, 0, (10, 2, -4), parent=parent, family_id=68
                )
            )
            self.assertTrue(
                habitat_destination_allowed(
                    527, 0, (2, 2, -4), parent=parent, family_id=30
                )
            )

    def test_reported_gobballs_can_move_on_native_surface_in_another_family_region(
        self,
    ):
        parent = dict(x=-45, y=16, z=0)
        self.assertTrue(
            habitat_destination_allowed(
                546, 0, (-44, 16, 0), parent=parent, family_id=68
            )
        )

    def test_unowned_native_surface_with_zero_capacity_is_allowed(self):
        with patch.dict(
            REGIONS,
            {(527, 7): {"monster_capacity": 0, "monster_families": []}},
            clear=True,
        ), patch("wakfu_server.planting_cells.surface", return_value={"region_id": 0}):
            self.assertTrue(habitat_destination_allowed(527, 0, (2, 2, -4)))

    def test_invalid_coordinates_still_fail_surface_validation(self):
        for destination in ((1.0, 2, 3), (True, 2, 3), (1, 2), None):
            with self.subTest(destination=destination):
                self.assertFalse(habitat_destination_allowed(527, 0, destination))
