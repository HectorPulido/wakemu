"""Native surfaces remain required regardless of regional family ownership."""

import unittest
import json
from contextlib import contextmanager, ExitStack
from unittest.mock import patch

from wakfu_server.monster_habitat_cells import habitat_destination_allowed
from wakfu_server import ecology_mobs
from wakfu_server.spatial_geometry import ImmutableIndex


@contextmanager
def native_habitat_sources(map_id, points):
    """Provide authored fixture source data to the actual shared Rust indexes."""
    habitats = ImmutableIndex(
        "geometry.load_habitats",
        lambda: dict(
            raw=json.dumps(
                [
                    dict(
                        map_id=map_id,
                        regions=[
                            dict(region_id=7, monster_capacity=0, monster_families=[])
                        ],
                    )
                ]
            )
        ),
    )
    surfaces = ImmutableIndex("geometry.index_points", lambda: dict(points=points))
    with ExitStack() as stack:
        for module in ("spatial_geometry", "monster_habitat_cells"):
            stack.enter_context(
                patch(f"wakfu_server.{module}.habitats", return_value=habitats)
            )
            stack.enter_context(
                patch(f"wakfu_server.{module}.surfaces", return_value=surfaces)
            )
        yield


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
        with native_habitat_sources(527, [(2, 2, -4), (10, 2, -4)]):
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
        # Zero ecological capacity does not remove a native walkable surface.
        with native_habitat_sources(527, [(2, 2, -4)]):
            self.assertTrue(habitat_destination_allowed(527, 0, (2, 2, -4)))

    def test_invalid_coordinates_still_fail_surface_validation(self):
        for destination in ((1.0, 2, 3), (True, 2, 3), (1, 2), None):
            with self.subTest(destination=destination):
                self.assertFalse(habitat_destination_allowed(527, 0, destination))

    def test_batched_habitat_matches_single_cell_guards_for_every_native_step(self):
        paths = {-1: [(2, 2, -4), (10, 2, -4)], -2: [(2, 2, -4)]}
        with native_habitat_sources(527, [(2, 2, -4), (10, 2, -4)]):
            self.assertTrue(ecology_mobs._native_habitat_paths_allowed((527, 0), paths))
            paths[-2].append((10, 2, -3))
            self.assertFalse(
                ecology_mobs._native_habitat_paths_allowed((527, 0), paths)
            )
            self.assertEqual(
                ecology_mobs._native_habitat_paths_allowed((527, 0), paths),
                all(
                    habitat_destination_allowed(527, 0, cell)
                    for path in paths.values()
                    for cell in path
                ),
            )
            self.assertTrue(
                ecology_mobs._native_habitat_paths_allowed((527, 12), paths)
            )
            self.assertTrue(
                ecology_mobs._native_habitat_paths_allowed((999999, 0), paths)
            )
