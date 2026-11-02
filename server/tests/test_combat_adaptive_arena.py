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
        stack.enter_context(
            patch(
                "wakfu_server.combat_terrain.selected_gap_indices",
                return_value={},
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
            patch(
                "wakfu_server.combat_terrain.selected_gap_indices",
                return_value={},
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

    def test_local_arena_empty_gap_mask_is_persisted_and_rebuilt(self):
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_placement_policy import _arena
        from wakfu_server.combat_arena_empty_gaps import POLICY

        cells = {
            (x, y, 0)
            for x in range(7)
            for y in range(7)
            if (x, y) not in {(3, 3), (4, 4)}
        }
        edges = {
            (cell, (cell[0] + dx, cell[1] + dy, 0))
            for cell in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (cell[0] + dx, cell[1] + dy, 0) in cells
        }
        selected = dict(
            cells=cells,
            edges=edges,
            placement={0: [(1, 1, 0)], 1: [(2, 1, 0)]},
            bounds=(0, 0, 6, 6),
        )
        placement = {0: {(0, 0, 0)}, 1: {(6, 6, 0)}}
        gaps = {(3, 3): 0}
        with (
            patch(
                "wakfu_server.combat_terrain.published_geometry",
                return_value=grid(7, 7),
            ),
            patch(
                "wakfu_server.combat_terrain.compact_encounter", return_value=selected
            ),
            patch(
                "wakfu_server.combat_terrain.safe_interior", return_value=(cells, set())
            ),
            patch("wakfu_server.combat_terrain.generate", return_value=placement),
            patch(
                "wakfu_server.combat_terrain.native_qi_surfaces", return_value=object()
            ),
            patch(
                "wakfu_server.combat_terrain.native_surface_indices",
                side_effect=lambda _surfaces, selected_cells: {
                    cell[:2]: 0 for cell in selected_cells
                },
            ),
            patch(
                "wakfu_server.combat_terrain.native_qi_surface_provenance",
                return_value={"map_id": 777},
            ),
            patch(
                "wakfu_server.combat_terrain.selected_gap_indices",
                side_effect=lambda _map_id, _cells, policy: gaps
                if policy == POLICY
                else self.fail("unexpected local arena gap policy"),
            ),
        ):
            initial = local_arena(
                777,
                90,
                (1, 1, 0),
                (2, 1, 0),
                variation_seed=0,
                minimum_dimensions=(7, 7),
            )

        hole = (3 - initial["x"]) + (3 - initial["y"]) * initial["width"]
        static_hole = (4 - initial["x"]) + (4 - initial["y"]) * initial["width"]
        self.assertEqual(initial["cell_masks"][hole], 0x200)
        self.assertEqual(initial["cell_masks"][static_hole], 0x100)
        self.assertEqual(initial["native_los_gap_policy"], POLICY)
        self.assertEqual(initial["native_los_gap_surfaces"], [[3, 3, 0]])

        layout = dict(
            cells=sorted(cells),
            edges=sorted(edges),
            placement={team: sorted(group) for team, group in placement.items()},
            wire_instance_id=90,
            native_los_gap_policy=initial["native_los_gap_policy"],
            native_los_gap_surfaces=initial["native_los_gap_surfaces"],
        )
        with (
            patch(
                "wakfu_server.combat_qi_surface_catalog.native_qi_surfaces",
                return_value=object(),
            ),
            patch(
                "wakfu_server.combat_qi_surface_catalog.native_qi_surface_provenance",
                return_value={"map_id": 777},
            ),
            patch(
                "wakfu_server.combat_qi_surface_selection.native_surface_indices",
                side_effect=lambda _surfaces, selected_cells: {
                    cell[:2]: 0 for cell in selected_cells
                },
            ),
            patch(
                "wakfu_server.combat_arena_empty_gaps.selected_gap_indices",
                return_value=gaps,
            ),
        ):
            rebuilt = _arena(777, 90, layout)
        rebuilt_hole = (3 - rebuilt["x"]) + (3 - rebuilt["y"]) * rebuilt["width"]
        rebuilt_static_hole = (4 - rebuilt["x"]) + (4 - rebuilt["y"]) * rebuilt["width"]
        self.assertEqual(rebuilt["cell_masks"][rebuilt_hole], 0x200)
        self.assertEqual(rebuilt["cell_masks"][rebuilt_static_hole], 0x100)

    def test_random_footprint_capacity_retries_maximum_then_border_once(self):
        from wakfu_server.combat_terrain import local_arena

        geometry = grid(20, 20)
        cells = {(x, y, 0) for x in range(6, 15) for y in range(6, 15)}
        edges = {
            (cell, (cell[0] + dx, cell[1] + dy, 0))
            for cell in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (cell[0] + dx, cell[1] + dy, 0) in cells
        }
        selected = dict(
            cells=cells,
            edges=edges,
            placement={0: [(10, 10, 0)], 1: [(11, 10, 0)]},
            bounds=(6, 6, 14, 14),
        )
        placements = {0: {(6, 6, 0)}, 1: {(14, 14, 0)}}
        calls = []

        def select(_geometry, _player, _members, **kwargs):
            calls.append(
                (
                    kwargs["minimum_dimensions"],
                    kwargs["allow_border_footprints"],
                    kwargs["player_slots"],
                )
            )
            if len(calls) < 3:
                raise ValueError(
                    "Native arena lacks disjoint ordinary actor footprint capacity"
                )
            return selected

        with (
            self.local_arena_fixtures(geometry),
            patch("wakfu_server.combat_terrain.compact_encounter", side_effect=select),
            patch(
                "wakfu_server.combat_terrain.safe_interior", return_value=(cells, set())
            ),
            patch("wakfu_server.combat_terrain.generate", return_value=placements),
            patch("wakfu_server.combat_terrain.random.Random") as seeded,
        ):
            seeded.return_value.randint.return_value = 7
            result = local_arena(
                777,
                90,
                (10, 10, 0),
                (11, 10, 0),
                variation_seed=90,
                size_range=(7, 9),
                automatic_cell_budget=100,
            )

        self.assertEqual(
            calls,
            [
                ((7, 7), False, 1),
                ((9, 9), False, 1),
                ((9, 9), True, 1),
                ((9, 9), False, 6),
            ],
        )
        self.assertEqual((result["width"], result["height"]), (9, 9))

        for options, error in (
            (
                {"minimum_dimensions": (7, 7)},
                "Native arena lacks disjoint ordinary actor footprint capacity",
            ),
            ({}, "Malformed native topology"),
        ):
            with self.subTest(options=options):
                rejected_calls = []

                def reject(_geometry, _player, _members, **kwargs):
                    rejected_calls.append(
                        (
                            kwargs["minimum_dimensions"],
                            kwargs["allow_border_footprints"],
                            kwargs["player_slots"],
                        )
                    )
                    raise ValueError(error)

                kwargs = dict(
                    variation_seed=90,
                    size_range=(7, 9),
                    automatic_cell_budget=100,
                    **options,
                )
                with (
                    patch(
                        "wakfu_server.combat_terrain.published_geometry",
                        return_value=geometry,
                    ),
                    patch(
                        "wakfu_server.combat_terrain.compact_encounter",
                        side_effect=reject,
                    ),
                    patch("wakfu_server.combat_terrain.random.Random") as seeded,
                ):
                    seeded.return_value.randint.return_value = 7
                    with self.assertRaisesRegex(ValueError, error):
                        local_arena(777, 90, (10, 10, 0), (11, 10, 0), **kwargs)
                self.assertEqual(len(rejected_calls), 1)
                self.assertFalse(rejected_calls[0][1])
                self.assertEqual(rejected_calls[0][2], 1)

    def test_random_maximum_refinement_improves_small_party_zone_or_keeps_first_layout(
        self,
    ):
        from wakfu_server.combat_terrain import local_arena

        geometry = grid(20, 20)

        def run(*, maximum_error=None):
            selection_calls = []
            generation_calls = []

            def select(_geometry, _player, _members, **kwargs):
                side = kwargs["minimum_dimensions"][0]
                selection_calls.append(side)
                if len(selection_calls) == 2 and maximum_error:
                    raise ValueError(maximum_error)
                cells = {
                    (x, y, 0)
                    for x in range(10 - side // 2, 10 - side // 2 + side)
                    for y in range(10 - side // 2, 10 - side // 2 + side)
                }
                edges = {
                    (cell, (cell[0] + dx, cell[1] + dy, 0))
                    for cell in cells
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if (cell[0] + dx, cell[1] + dy, 0) in cells
                }
                return {
                    "cells": cells,
                    "edges": edges,
                    "placement": {0: [(10, 10, 0)], 1: [(11, 10, 0)]},
                    "participant_positions": [((11, 10, 0), (11, 10, 0))],
                    "bounds": (
                        min(x for x, _, _ in cells),
                        min(y for _, y, _ in cells),
                        max(x for x, _, _ in cells),
                        max(y for _, y, _ in cells),
                    ),
                }

            def generate(*_args, **_kwargs):
                generation_calls.append(1)
                count = 3 if len(generation_calls) == 1 else 6
                return {
                    0: {(7 + x, 7, 0) for x in range(count)},
                    1: {(7 + x, 13, 0) for x in range(count)},
                }

            with (
                self.local_arena_fixtures(geometry),
                patch(
                    "wakfu_server.combat_terrain.compact_encounter", side_effect=select
                ),
                patch(
                    "wakfu_server.combat_terrain.safe_interior",
                    side_effect=lambda cells, *_a, **_k: (cells, set()),
                ),
                patch("wakfu_server.combat_terrain.generate", side_effect=generate),
                patch("wakfu_server.combat_terrain.random.Random") as seeded,
            ):
                seeded.return_value.randint.return_value = 7
                result = local_arena(
                    777,
                    90,
                    (10, 10, 0),
                    (11, 10, 0),
                    variation_seed=90,
                    size_range=(7, 9),
                    automatic_cell_budget=100,
                )
            return result, selection_calls

        improved, improved_calls = run()
        self.assertEqual(improved_calls, [7, 9])
        self.assertEqual((improved["width"], improved["height"]), (9, 9))
        self.assertEqual(len(improved["placement_cells"][0]), 6)
        self.assertEqual(len(improved["placement_cells"][1]), 6)
        self.assertFalse(
            improved["placement_cells"][0] & improved["placement_cells"][1]
        )
        self.assertFalse(
            (improved["placement_cells"][0] | improved["placement_cells"][1])
            & improved["native_border_cells"]
        )
        self.assertTrue(improved["validated_cells"] <= geometry["cells"])

        retained, retained_calls = run(maximum_error="Malformed native topology")
        self.assertEqual(retained_calls, [7, 9])
        self.assertEqual((retained["width"], retained["height"]), (7, 7))
        self.assertEqual(len(retained["placement_cells"][0]), 3)
        self.assertEqual(len(retained["placement_cells"][1]), 3)
        self.assertFalse(
            (retained["placement_cells"][0] | retained["placement_cells"][1])
            & retained["native_border_cells"]
        )

    def test_six_native_party_positions_freeze_replay_and_reject_tampering(self):
        from wakfu_server.combat_arena_selection import (
            compact_encounter,
            cardinal_border_cells,
        )
        from wakfu_server.combat_placement_footprints import covered_cells
        from wakfu_server.combat_placement_policy import _arena, _party_reserved_cells

        geometry = grid(20, 20)
        selected = compact_encounter(
            geometry,
            (10, 10, 0),
            [(11, 10, 0)],
            minimum_cells=25,
            minimum_dimensions=(15, 15),
            dimensions_include_border=True,
            automatic_cell_budget=100,
            member_radii=(1,),
            player_slots=6,
            allow_border_footprints=True,
        )
        reserved = [list(cell) for cell in selected["party_reserved_cells"]]
        npc_cells = set()
        for _, position in selected["participant_positions"]:
            npc_cells.update(covered_cells(position, 1, selected["cells"]))
        record = {
            "cells": sorted(selected["cells"]),
            "edges": sorted(selected["edges"]),
            "placement": {
                team: sorted(group) for team, group in selected["placement"].items()
            },
            "wire_instance_id": 90,
            "native_border_cells": sorted(cardinal_border_cells(selected["cells"])),
            "native_party_reserved_cells": reserved,
            "native_party_npc_cells": [list(cell) for cell in sorted(npc_cells)],
        }
        player_zone = {tuple(cell) for cell in record["placement"][0]}
        self.assertEqual(len(reserved), 6)
        self.assertTrue(set(map(tuple, reserved)) <= player_zone)
        self.assertFalse(player_zone & npc_cells)
        self.assertFalse(set(map(tuple, reserved)) & npc_cells)
        self.assertEqual(
            _party_reserved_cells(record, selected["cells"], selected["placement"], 0),
            set(map(tuple, reserved)),
        )

        indices = {cell[:2]: 0 for cell in selected["cells"]}
        expected = arena(
            777,
            90,
            sorted(selected["cells"]),
            selected["placement"],
            surface_indices=indices,
            border_cells=record["native_border_cells"],
        )
        with (
            patch(
                "wakfu_server.combat_qi_surface_catalog.native_qi_surfaces",
                return_value=object(),
            ),
            patch(
                "wakfu_server.combat_qi_surface_catalog.native_qi_surface_provenance",
                return_value={"map_id": 777},
            ),
            patch(
                "wakfu_server.combat_qi_surface_selection.native_surface_indices",
                return_value=indices,
            ),
            patch(
                "wakfu_server.combat_arena_empty_gaps.restored_gap_indices",
                return_value={},
            ),
        ):
            replayed = _arena(777, 90, record)
        self.assertEqual(expected["cell_masks"], replayed["cell_masks"])
        self.assertEqual(expected["cell_flags"], replayed["cell_flags"])
        self.assertEqual(
            record["native_party_reserved_cells"],
            replayed["native_party_reserved_cells"],
        )
        self.assertEqual(
            record["native_party_npc_cells"], replayed["native_party_npc_cells"]
        )

        invalid_records = []
        invalid_records.append({**record, "native_party_npc_cells": None})
        invalid_records.append({**record, "native_party_reserved_cells": reserved[:-1]})
        invalid_records.append(
            {
                **record,
                "native_border_cells": [*record["native_border_cells"], reserved[0]],
            }
        )
        invalid_records.append(
            {
                **record,
                "placement": {
                    0: [*record["placement"][0], record["native_party_npc_cells"][0]],
                    1: record["placement"][1],
                },
            }
        )
        invalid_records.append(
            {
                **record,
                "native_party_reserved_cells": [[999, 999, 0], *reserved[1:]],
            }
        )
        for tampered in invalid_records:
            with self.subTest(tampered=tampered), self.assertRaises(ValueError):
                _party_reserved_cells(
                    tampered,
                    set(map(tuple, tampered["cells"])),
                    {
                        team: set(map(tuple, group))
                        for team, group in tampered["placement"].items()
                    },
                    0,
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
