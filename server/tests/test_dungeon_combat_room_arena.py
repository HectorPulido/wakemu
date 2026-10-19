"""Pure regressions for combat terrain scoped to a pinned dungeon room."""
import unittest
import importlib.util
import sys
from types import ModuleType
from pathlib import Path
from unittest.mock import patch

MAP_ID = 1087
INSTANCE_ID = 41
GROUP_ID = 902
ROOM_ONE = {(x, y, 0) for x in range(10) for y in range(10)}
ROOM_TWO = {(x, y, 0) for x in range(10, 20) for y in range(10)}


def native_geometry():
    cells = ROOM_ONE | ROOM_TWO
    edges = [
        (cell, (cell[0] + dx, cell[1] + dy, 0))
        for cell in cells
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if (cell[0] + dx, cell[1] + dy, 0) in cells
        and not ({cell[0], cell[0] + dx} == {9, 10} and cell[1] != 5)
    ]
    # The two rooms touch at x=9/x=10, but the closed gate has no native edge.
    return {"map_id": MAP_ID, "cells": cells, "edges": edges}


def config():
    return {
        "topology": {
            "asset_map_id": MAP_ID,
            "policy": "native_physical_door_victory_policy",
            "rooms": [
                {"order": 1, "anchor": (1, 1, 0), "cells": sorted(ROOM_ONE)},
                {"order": 2, "anchor": (18, 8, 0), "cells": sorted(ROOM_TWO)},
            ],
        }
    }


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class RoomDb:
    def __init__(self, progress=None, receipt=None):
        self.progress = progress or {"current_room": 1, "status": "active"}
        self.receipt = receipt or {"asset_map_id": MAP_ID, "group_id": GROUP_ID}

    def execute(self, query, params):
        if "SELECT current_room,status" in query:
            return Result(self.progress)
        if "dungeon_room_spawn_receipts" in query:
            return Result(self.receipt)
        raise AssertionError("Unexpected SQL in pure dungeon scope test: " + query)


class DungeonCombatRoomArenaTests(unittest.TestCase):
    @staticmethod
    def runtime():
        # Importing the full dungeon service graph initializes the native
        # monster catalog. These tests exercise only pure geometry and room
        # selection, so satisfy runtime's unused service imports with stubs.
        names = (
            "wakfu_server.dungeon_progression",
            "wakfu_server.dungeon_room_spawns",
            "wakfu_server.dungeon_runtime_config",
        )
        stubs = {name: ModuleType(name) for name in names}
        import wakfu_server

        attributes = {name.rsplit(".", 1)[-1] for name in names}
        missing = object()
        previous = {name: getattr(wakfu_server, name, missing) for name in attributes}
        try:
            with patch.dict(sys.modules, stubs):
                path = (
                    Path(__file__).resolve().parents[1]
                    / "wakfu_server/maps/dungeon_runtime.py"
                )
                spec = importlib.util.spec_from_file_location(
                    "_dungeon_runtime_pure_scope_test", path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
        finally:
            for name, value in previous.items():
                if value is missing:
                    if hasattr(wakfu_server, name):
                        delattr(wakfu_server, name)
                else:
                    setattr(wakfu_server, name, value)

    def allowed_room(self):
        dungeon_runtime = self.runtime()
        with patch.object(
            dungeon_runtime, "configuration_for_instance", return_value=(None, config())
        ):
            return dungeon_runtime.combat_room_cells(
                RoomDb(),
                (MAP_ID, INSTANCE_ID, GROUP_ID),
                (1, 1, 0),
                [(8, 8, 0)],
            )

    def local_arena(self, allowed_cells=None, **kwargs):
        from wakfu_server.combat import combat_terrain

        geometry = native_geometry()
        with (
            patch.object(combat_terrain, "published_geometry", return_value=geometry),
            patch.object(combat_terrain, "native_qi_surfaces", return_value=object()),
            patch.object(
                combat_terrain,
                "native_surface_indices",
                side_effect=lambda _surfaces, cells: {cell[:2]: 0 for cell in cells},
            ),
            patch.object(
                combat_terrain,
                "native_qi_surface_provenance",
                return_value={"map_id": MAP_ID},
            ),
        ):
            return combat_terrain.local_arena(
                MAP_ID,
                55,
                (1, 1, 0),
                [(8, 8, 0)],
                compact=False,
                allowed_cells=allowed_cells,
                **kwargs,
            )

    def test_current_group_and_participants_resolve_only_to_pinned_room(self):
        dungeon_runtime = self.runtime()
        allowed = self.allowed_room()
        self.assertEqual(ROOM_ONE, set(allowed))
        with patch.object(
            dungeon_runtime, "configuration_for_instance", return_value=(None, config())
        ):
            with self.assertRaisesRegex(ValueError, "current dungeon room"):
                dungeon_runtime.combat_room_cells(
                    RoomDb(receipt={"asset_map_id": MAP_ID, "group_id": GROUP_ID + 1}),
                    (MAP_ID, INSTANCE_ID, GROUP_ID),
                    (1, 1, 0),
                    [(8, 8, 0)],
                )
            with self.assertRaisesRegex(ValueError, "outside its pinned room"):
                dungeon_runtime.combat_room_cells(
                    RoomDb(),
                    (MAP_ID, INSTANCE_ID, GROUP_ID),
                    (1, 1, 0),
                    [(18, 8, 0)],
                )

    def test_wrong_map_and_empty_scope_fail_closed(self):
        dungeon_runtime = self.runtime()
        with patch.object(
            dungeon_runtime, "configuration_for_instance", return_value=(None, config())
        ):
            with self.assertRaisesRegex(ValueError, "current dungeon room"):
                dungeon_runtime.combat_room_cells(
                    RoomDb(),
                    (MAP_ID + 1, INSTANCE_ID, GROUP_ID),
                    (1, 1, 0),
                    [(8, 8, 0)],
                )
        with self.assertRaisesRegex(ValueError, "Combat room cells"):
            self.local_arena(set())

    def test_arena_and_placement_stay_in_pinned_room_without_crossing_closed_gate(self):
        result = self.local_arena(self.allowed_room())
        selected = set(result["validated_cells"])
        placements = set(result["placement_cells"][0]) | set(
            result["placement_cells"][1]
        )
        self.assertTrue(selected)
        self.assertTrue(selected <= ROOM_ONE)
        self.assertTrue(placements <= ROOM_ONE)
        self.assertFalse(
            any(
                start in ROOM_ONE and end in ROOM_TWO
                for start, end in result["valid_edges"]
            )
        )
        self.assertIn((1, 1, 0), selected)
        self.assertIn((8, 8, 0), selected)

    def test_compact_selection_without_room_scope_would_cross_the_closed_gate(self):
        from wakfu_server.combat import combat_terrain

        geometry = native_geometry()
        player, monster = (9, 4, 0), (9, 5, 0)
        with (
            patch.object(combat_terrain, "published_geometry", return_value=geometry),
            patch.object(combat_terrain, "native_qi_surfaces", return_value=object()),
            patch.object(
                combat_terrain,
                "native_surface_indices",
                side_effect=lambda _surfaces, cells: {cell[:2]: 0 for cell in cells},
            ),
            patch.object(
                combat_terrain,
                "native_qi_surface_provenance",
                return_value={"map_id": MAP_ID},
            ),
        ):
            unscoped = combat_terrain.local_arena(
                MAP_ID,
                55,
                player,
                [monster],
                compact=True,
                variation_seed=0,
                size_range=(7, 10),
            )
            scoped = combat_terrain.local_arena(
                MAP_ID,
                55,
                player,
                [monster],
                compact=True,
                variation_seed=0,
                size_range=(7, 10),
                allowed_cells=ROOM_ONE,
            )
        self.assertTrue(set(unscoped["validated_cells"]) & ROOM_TWO)
        self.assertTrue(set(scoped["validated_cells"]) <= ROOM_ONE)
        self.assertTrue(
            set(scoped["placement_cells"][0]) | set(scoped["placement_cells"][1])
            <= ROOM_ONE
        )

    def test_selected_branch_room_bounds_combat_scope(self):
        dungeon_runtime = self.runtime()
        from wakfu_server import dungeon_branches

        room_cells = [
            ([(0, 0, 0), (1, 0, 0)], (0, 0, 0)),
            ([(10, 0, 0), (11, 0, 0), (18, 0, 0), (19, 0, 0)], (10, 0, 0)),
        ]
        selected_cells = [(10, 0, 0), (11, 0, 0)]
        other_cells = [(18, 0, 0), (19, 0, 0)]
        branch_topology = {
            "asset_map_id": MAP_ID,
            "policy": "native_mixed_victory_policy",
            "selected_branch": "left",
            "rooms": [
                {"order": order, "anchor": anchor, "cells": cells}
                for order, (cells, anchor) in enumerate(room_cells, 1)
            ],
            "doors": [
                {"source_id": 1, "source_room": 1, "destination_room": 1},
                {"source_id": 2, "source_room": 1, "destination_room": 1},
            ],
            "physical_doors": [
                {"source_id": 10, "position": (2, 0, 0)},
                {"source_id": 11, "position": (3, 0, 0)},
            ],
            "branch_routes": [
                {
                    "key": "left",
                    "source_ids": [1],
                    "entry_source_id": 1,
                    "physical_source_ids": [10],
                    "rooms": [
                        {
                            "order": 1,
                            "cells": room_cells[0][0],
                            "anchor": (0, 0, 0),
                            "native_arrival": (0, 0, 0),
                        },
                        {
                            "order": 2,
                            "cells": selected_cells,
                            "anchor": selected_cells[0],
                            "native_arrival": selected_cells[0],
                        },
                    ],
                },
                {
                    "key": "right",
                    "source_ids": [2],
                    "entry_source_id": 2,
                    "physical_source_ids": [11],
                    "rooms": [
                        {
                            "order": 1,
                            "cells": room_cells[0][0],
                            "anchor": (0, 0, 0),
                            "native_arrival": (0, 0, 0),
                        },
                        {
                            "order": 2,
                            "cells": other_cells,
                            "anchor": other_cells[0],
                            "native_arrival": other_cells[0],
                        },
                    ],
                },
            ],
        }
        with patch.object(
            dungeon_runtime,
            "configuration_for_instance",
            return_value=(None, {"topology": branch_topology}),
        ):
            scope = dungeon_runtime.combat_room_cells(
                RoomDb(progress={"current_room": 2, "status": "active"}),
                (MAP_ID, INSTANCE_ID, GROUP_ID),
                selected_cells[0],
                [selected_cells[1]],
            )
        self.assertEqual(set(selected_cells), set(scope))
        self.assertTrue(set(other_cells).isdisjoint(scope))
        self.assertEqual(
            set(selected_cells),
            set(dungeon_branches.selected_room(branch_topology, 2)["cells"]),
        )

    def test_shared_arena_scope_tracks_current_encounter_stage(self):
        dungeon_runtime = self.runtime()
        shared_cells = {(x, y, 0) for x in range(7) for y in range(7)}
        shared_topology = {
            "asset_map_id": MAP_ID,
            "policy": "native_shared_arena_sequential_policy",
            "rooms": [
                {"order": order, "anchor": (1, 1, 0), "cells": sorted(shared_cells)}
                for order in (1, 2, 3)
            ],
            "branch_routes": [],
        }
        with patch.object(
            dungeon_runtime,
            "configuration_for_instance",
            return_value=(None, {"topology": shared_topology}),
        ):
            scope = dungeon_runtime.combat_room_cells(
                RoomDb(progress={"current_room": 2, "status": "active"}),
                (MAP_ID, INSTANCE_ID, GROUP_ID),
                (1, 1, 0),
                [(5, 5, 0)],
            )
        self.assertEqual(shared_cells, set(scope))
        self.assertEqual(2, shared_topology["rooms"][1]["order"])

    def test_ordinary_map_call_keeps_full_native_geometry_behavior(self):
        baseline = self.local_arena(None, variation_seed=13)
        ordinary = self.local_arena(variation_seed=13)
        self.assertEqual(baseline["validated_cells"], ordinary["validated_cells"])
        self.assertEqual(baseline["valid_edges"], ordinary["valid_edges"])
        self.assertEqual(baseline["placement_cells"], ordinary["placement_cells"])


if __name__ == "__main__":
    unittest.main()
