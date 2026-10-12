"""Native outdoor ownership is stricter than walking reachability."""
import unittest
from unittest.mock import patch

from wakfu_server.monster_habitat_cells import habitat_destination_allowed
from wakfu_server.monster_initial_population import REGIONS


class MonsterHabitatCellTests(unittest.TestCase):
    def test_reported_gobball_border_cell_is_not_a_native_birth_surface(self):
        parent = dict(x=-162, y=-125, z=-4)
        self.assertTrue(
            habitat_destination_allowed(527, 0, (-162, -125, -4), parent=parent)
        )
        self.assertFalse(
            habitat_destination_allowed(527, 0, (-163, -125, -4), parent=parent)
        )

    def test_unknown_maps_and_private_instances_keep_existing_reachability_policy(self):
        self.assertTrue(habitat_destination_allowed(527, 17, (-163, -125, -4)))
        self.assertTrue(habitat_destination_allowed(999999, 0, (1, 2, 3)))

    def test_known_outdoor_cell_requires_exact_native_region_height_and_family(self):
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
            self.assertFalse(
                habitat_destination_allowed(
                    527, 0, (10, 2, -4), parent=parent, family_id=68
                )
            )
            self.assertFalse(
                habitat_destination_allowed(
                    527, 0, (2, 2, -4), parent=parent, family_id=30
                )
            )
