import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from wakfu_server.combat_arena_selection import compact_encounter
from wakfu_server.combat_placement_cells import generate
from wakfu_server.combat_wire import arena, decode_topology, topology as encode_topology
from wakfu_server.combat_arena_selection import cardinal_border_cells


def grid(width, height):
    cells = {(x, y, 0) for x in range(width) for y in range(height)}
    edges = [
        (cell, (cell[0] + dx, cell[1] + dy, 0))
        for cell in cells
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if (cell[0] + dx, cell[1] + dy, 0) in cells
    ]
    return {"map_id": 777, "cells": cells, "edges": edges}


class AdaptiveArenaTests(unittest.TestCase):
    def local_arena_fixtures(self, geometry):
        stack = ExitStack()
        stack.enter_context(
            patch(
                "wakfu_server.combat_terrain.published_geometry", return_value=geometry
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_terrain.native_qi_surfaces", return_value=object()
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_terrain.native_surface_indices",
                side_effect=lambda surfaces, cells: {
                    (cell[0], cell[1]): 0 for cell in cells
                },
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_terrain.native_qi_surface_provenance",
                return_value={"map_id": 777},
            )
        )
        return stack

    def test_directed_detour_expands_until_selected_prefix_is_mutually_reachable(self):
        # This 28-cell perimeter is one directed cycle. The first 25-cell BFS
        # prefix has no return path to the player, so automatic sizing must
        # continue to the cycle closure rather than keep a one-way arena.
        path = (
            [(x, 0, 0) for x in range(8)]
            + [(7, y, 0) for y in range(1, 8)]
            + [(x, 7, 0) for x in range(6, -1, -1)]
            + [(0, y, 0) for y in range(6, 0, -1)]
        )
        edges = list(zip(path, path[1:])) + [(path[-1], path[0])]
        result = compact_encounter(
            {"map_id": 777, "cells": path, "edges": edges}, path[0], [path[1]]
        )
        self.assertEqual(result["cells"], set(path))
        self.assertEqual(result["edges"], set(edges))

    def test_explicit_budget_keeps_legacy_budget_instead_of_automatic_minimum(self):
        result = compact_encounter(grid(8, 8), (0, 0, 0), [(7, 7, 0)], cell_budget=18)
        self.assertLessEqual(len(result["cells"]), 18)
        self.assertLessEqual(
            (result["bounds"][2] - result["bounds"][0] + 1)
            * (result["bounds"][3] - result["bounds"][1] + 1),
            18,
        )

    def test_25_cell_open_arena_has_12_placement_slots_each_and_wire_flags(self):
        result = compact_encounter(grid(10, 10), (0, 0, 0), [(9, 9, 0)], cell_budget=25)
        self.assertEqual(len(result["cells"]), 25)
        zones = generate(
            result["cells"],
            result["edges"],
            {0: result["placement"][0], 1: result["placement"][1]},
            slots_per_team=12,
        )
        self.assertEqual(tuple(map(len, (zones[0], zones[1]))), (12, 12))
        self.assertFalse(zones[0] & zones[1])
        self.assertTrue(zones[0] | zones[1] <= result["cells"])

        message = encode_topology(arena(777, 1, sorted(result["cells"]), zones))
        decoded = decode_topology(message)
        self.assertEqual(decoded["cell_flags"].count(0), 12)
        self.assertEqual(decoded["cell_flags"].count(1), 12)
        self.assertEqual(
            decoded["cell_flags"].count(255), decoded["width"] * decoded["height"] - 24
        )

    def test_all_fourteen_seeded_square_sizes_have_outer_border_and_twelve_slots(self):
        from wakfu_server.combat_terrain import local_arena

        geometry = grid(30, 30)
        with (
            patch(
                "wakfu_server.combat_terrain.published_geometry", return_value=geometry
            ),
            patch(
                "wakfu_server.combat_terrain.native_qi_surfaces",
                return_value=object(),
            ),
            patch(
                "wakfu_server.combat_terrain.native_surface_indices",
                side_effect=lambda surfaces, cells: {
                    (cell[0], cell[1]): 0 for cell in cells
                },
            ),
            patch(
                "wakfu_server.combat_terrain.native_qi_surface_provenance",
                return_value={"map_id": 777},
            ),
        ):
            for side in range(7, 21):
                with self.subTest(side=side):
                    instances = []

                    def formation(seed):
                        self.assertEqual(seed, 90)
                        instance = Mock()
                        instance.randint.return_value = side
                        instances.append(instance)
                        return instance

                    with patch(
                        "wakfu_server.combat_terrain.random.Random",
                        side_effect=formation,
                    ) as seeded_random:
                        result = local_arena(
                            777,
                            90,
                            (15, 15, 0),
                            (16, 15, 0),
                            variation_seed=90,
                        )
                    seeded_random.assert_called_once_with(90)
                    instances[0].randint.assert_called_once_with(7, 20)
                    self.assertEqual((result["width"], result["height"]), (side, side))
                    self.assertGreaterEqual(
                        len(result["validated_cells"]),
                        max((side - 2) ** 2, 25),
                    )
                    zones = result["placement_cells"]
                    self.assertEqual(len(zones[0]), 12)
                    self.assertEqual(len(zones[1]), 12)
                    self.assertFalse(zones[0] & zones[1])
                    self.assertFalse(
                        (zones[0] | zones[1])
                        & cardinal_border_cells(result["validated_cells"])
                    )
                    self.assertFalse(
                        (zones[0] | zones[1]) & result["native_border_cells"]
                    )

    def test_random_size_draw_is_seeded_once_and_retry_repeats_exact_arena(self):
        from wakfu_server.combat_terrain import local_arena

        geometry = grid(40, 40)
        with self.local_arena_fixtures(geometry):
            first = local_arena(777, 90, (20, 20, 0), (21, 20, 0), variation_seed=90)
            retry = local_arena(777, 90, (20, 20, 0), (21, 20, 0), variation_seed=90)
        self.assertEqual(first["validated_cells"], retry["validated_cells"])
        self.assertEqual(first["placement_cells"], retry["placement_cells"])
        self.assertEqual(first["cell_masks"], retry["cell_masks"])

    def test_random_size_range_clamps_to_budget_and_rejects_invalid_policy(self):
        from wakfu_server.combat_terrain import local_arena

        geometry = grid(20, 20)
        with self.local_arena_fixtures(geometry):
            with patch("wakfu_server.combat_terrain.random.Random") as seeded:
                seeded.return_value.randint.return_value = 7
                result = local_arena(
                    777,
                    1,
                    (10, 10, 0),
                    (11, 10, 0),
                    variation_seed=1,
                    size_range=(7, 20),
                    automatic_cell_budget=49,
                )
                seeded.return_value.randint.assert_called_once_with(7, 7)
                self.assertEqual((result["width"], result["height"]), (7, 7))
            for invalid in ((6, 20), (21, 20), (7, 51), (7, 20, 21), (7, 7.0)):
                with self.subTest(size_range=invalid), self.assertRaises(ValueError):
                    local_arena(
                        777,
                        1,
                        (10, 10, 0),
                        (11, 10, 0),
                        variation_seed=1,
                        size_range=invalid,
                    )

    def test_irregular_terrain_keeps_native_cap_and_explicit_duel_dimensions_legacy(
        self,
    ):
        # A large open component with a wall opening exercises the irregular
        # crop path; the selected geometry must stay inside both native terrain
        # and the configured area budget.
        cells = {(x, y, 0) for x in range(40) for y in range(40) if x != 20 or y == 20}
        edges = [
            (cell, (cell[0] + dx, cell[1] + dy, 0))
            for cell in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (cell[0] + dx, cell[1] + dy, 0) in cells
        ]
        geometry = {"map_id": 777, "cells": cells, "edges": edges}
        with self.local_arena_fixtures(geometry):
            selected = compact_encounter(
                geometry,
                (8, 20, 0),
                [(9, 20, 0)],
                minimum_cells=25,
                minimum_dimensions=(7, 7),
                dimensions_include_border=True,
                automatic_cell_budget=49,
            )
        self.assertLessEqual(len(selected["cells"]), 49)
        self.assertTrue(selected["cells"] <= cells)
        self.assertEqual(
            (selected["bounds"][2] - selected["bounds"][0] + 1)
            * (selected["bounds"][3] - selected["bounds"][1] + 1),
            49,
        )

        duel = compact_encounter(
            grid(45, 45),
            (20, 20, 0),
            [(22, 20, 0)],
            minimum_cells=900,
            minimum_dimensions=(30, 30),
            automatic_cell_budget=900,
        )
        self.assertEqual(len(duel["cells"]), 900)

    def test_corridor_falls_back_to_native_edge_slots_without_entry_failure(self):
        from wakfu_server.combat_terrain import local_arena

        cells = {(x, y, 0) for x in range(3) for y in range(20)}
        edges = [
            (cell, (cell[0] + dx, cell[1] + dy, 0))
            for cell in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (cell[0] + dx, cell[1] + dy, 0) in cells
        ]
        geometry = {"map_id": 777, "cells": cells, "edges": edges}
        with self.local_arena_fixtures(geometry):
            result = local_arena(777, 41, (1, 1, 0), (1, 18, 0), variation_seed=7)

        zones = result["placement_cells"]
        self.assertEqual(len(zones[0]), 12)
        self.assertEqual(len(zones[1]), 12)
        self.assertFalse(zones[0] & zones[1])
        self.assertTrue((zones[0] | zones[1]) <= result["validated_cells"])
        raw_perimeter = cardinal_border_cells(result["validated_cells"])
        self.assertTrue((zones[0] | zones[1]) & raw_perimeter)
        self.assertFalse((zones[0] | zones[1]) & result["native_border_cells"])

    def test_relocated_encounter_stays_on_local_side_of_native_wall(self):
        from wakfu_server.combat_terrain import local_arena

        cells = {(x, y, 0) for x in range(20) for y in range(20) if x != 10 or y == 10}
        edges = [
            (cell, (cell[0] + dx, cell[1] + dy, 0))
            for cell in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (cell[0] + dx, cell[1] + dy, 0) in cells
        ]
        geometry = {"map_id": 777, "cells": cells, "edges": edges}
        with self.local_arena_fixtures(geometry):
            result = local_arena(
                777,
                42,
                (8, 10, 0),
                (12, 10, 0),
                variation_seed=12,
                minimum_dimensions=(5, 5),
            )

        zones = result["placement_cells"]
        self.assertEqual(len(zones[0]), 12)
        self.assertEqual(len(zones[1]), 12)
        self.assertTrue(all(cell[0] < 10 for cell in result["validated_cells"]))
        self.assertNotIn((12, 10, 0), zones[1])
        self.assertFalse(zones[0] & zones[1])
        self.assertFalse(
            (zones[0] | zones[1]) & cardinal_border_cells(result["validated_cells"])
        )
        self.assertFalse((zones[0] | zones[1]) & result["native_border_cells"])

    def test_open_map_keeps_reachable_enemy_at_distance_ten_and_twelve_slots(self):
        result = compact_encounter(
            grid(20, 20),
            (0, 0, 0),
            [(10, 0, 0)],
            minimum_cells=25,
            minimum_dimensions=(5, 5),
        )
        self.assertEqual(result["placement"][1], [(10, 0, 0)])
        zones = generate(
            result["cells"],
            result["edges"],
            result["placement"],
            slots_per_team=12,
        )
        self.assertEqual(len(zones[0]), 12)
        self.assertEqual(len(zones[1]), 12)
        self.assertIn((10, 0, 0), zones[1])
        self.assertGreaterEqual(len(result["cells"]), 36)

    def test_same_encounter_identity_retries_same_formation(self):
        from wakfu_server.combat_terrain import local_arena

        geometry = grid(12, 12)
        with (
            patch(
                "wakfu_server.combat_terrain.published_geometry", return_value=geometry
            ),
            patch(
                "wakfu_server.combat_terrain.native_qi_surfaces", return_value=object()
            ),
            patch(
                "wakfu_server.combat_terrain.native_surface_indices",
                side_effect=lambda surfaces, cells: {
                    (cell[0], cell[1]): 0 for cell in cells
                },
            ),
            patch(
                "wakfu_server.combat_terrain.native_qi_surface_provenance",
                return_value={"map_id": 777},
            ),
        ):
            first = local_arena(
                777, 314159, (0, 0, 0), (1, 0, 0), variation_seed=314159
            )
            retry = local_arena(
                777, 314159, (0, 0, 0), (1, 0, 0), variation_seed=314159
            )
        self.assertEqual(first["validated_cells"], retry["validated_cells"])
        self.assertEqual(first["placement_cells"], retry["placement_cells"])
        self.assertEqual(first["cell_masks"], retry["cell_masks"])


if __name__ == "__main__":
    unittest.main()
