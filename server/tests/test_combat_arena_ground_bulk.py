"""Arena bulk ground filtering preserves the per-cell native policy and fallbacks."""
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import wakfu_server.combat_ground_support as combat_ground_support
import wakfu_server.combat_terrain as combat_terrain
from wakfu_server.combat_sn_path import NativeSnColumns


MAP_ID = 777
SOURCE_SHA256 = "eb36ad4b882069928893bdd5d7a0a360adcef2e71ce23f65386f446393dc0835"


class StopAfterSelection(Exception):
    pass


class ArenaGroundBulkTests(unittest.TestCase):
    @staticmethod
    def fixture():
        geometry = {
            "map_id": MAP_ID,
            "cells": {(x, y, 0) for x in range(7) for y in range(7)},
            "edges": [],
        }
        all_cells = geometry["cells"]
        allowed = all_cells - {(3, 3, 0)}
        columns_data = {
            "schema": "native-Sn-Vy-columns-v1",
            "map_id": MAP_ID,
            "source_sha256": SOURCE_SHA256,
            "chunks": [
                {
                    "x": 0,
                    "y": 0,
                    "width": 18,
                    "height": 18,
                    "columns": [
                        [x, y, [[0, 0, 0, 0, 0, False]]]
                        for x in range(7)
                        for y in range(7)
                    ],
                }
            ],
        }
        columns = NativeSnColumns(
            columns_data, map_id=MAP_ID, source_sha256=SOURCE_SHA256
        )
        publication = {
            "qualified_native_release": "arena-ground-test",
            "maps": {
                str(MAP_ID): {
                    "map_id": MAP_ID,
                    "status": "exported",
                    "source_sha256": SOURCE_SHA256,
                    "supported_cells": [list(cell) for cell in sorted(allowed)],
                    "unknown_material_cells": [],
                }
            },
        }
        captured = []

        def select(*args, **kwargs):
            captured.append(kwargs)
            raise StopAfterSelection()

        return geometry, allowed, columns, publication, captured, select

    def _run(self, *, fallback):
        geometry, allowed, columns, publication, captured, select = self.fixture()
        patches = [
            patch.object(combat_terrain, "published_geometry", return_value=geometry),
            patch.object(
                combat_terrain,
                "native_qi_surface_provenance",
                return_value={
                    "map_id": MAP_ID,
                    "source_sha256": SOURCE_SHA256,
                },
            ),
            patch.object(
                combat_terrain.protocol_catalog,
                "release",
                return_value="arena-ground-test",
            ),
            patch.object(combat_terrain, "compact_encounter", side_effect=select),
            patch.object(NativeSnColumns, "from_published", return_value=columns),
            patch.object(combat_ground_support, "_catalog", return_value=publication),
        ]
        if fallback:
            patches.append(
                patch.object(
                    combat_ground_support,
                    "supported",
                    side_effect=lambda map_id, cell, source: cell in allowed,
                )
            )
        combat_ground_support._map.cache_clear()
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            with self.assertRaises(StopAfterSelection):
                combat_terrain.local_arena(
                    MAP_ID,
                    19,
                    (1, 1, 0),
                    (5, 5, 0),
                    compact=True,
                    ordinary_npc_placement=True,
                    size_range=(7, 7),
                    automatic_cell_budget=49,
                )
        self.assertEqual(len(captured), 1)
        return captured[0]

    def test_bulk_and_original_provider_build_identical_native_ground_sets(self):
        bulk = self._run(fallback=False)
        fallback = self._run(fallback=True)
        expected = {(x, y, 0) for x in range(7) for y in range(7)} - {(3, 3, 0)}
        self.assertEqual(bulk["placement_ground_cells"], expected)
        self.assertEqual(fallback["placement_ground_cells"], expected)
        self.assertEqual(
            bulk["placement_ground_cells"], fallback["placement_ground_cells"]
        )
        self.assertEqual(bulk["member_point_cells"], fallback["member_point_cells"])
        self.assertNotIn((3, 3, 0), bulk["member_point_cells"])


if __name__ == "__main__":
    unittest.main()
