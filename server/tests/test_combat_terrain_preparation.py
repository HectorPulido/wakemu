"""Validated terrain sources can be retained across the duel lock boundary."""
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch
from wakfu_server.combat.combat_terrain import (
    PreparedTerrain,
    prepare_terrain,
    local_arena,
)
from wakfu_server.combat.combat_geometry import prepare_geometry


class TerrainPreparationTests(unittest.TestCase):
    def geometry(self):
        cells = [(x, y, 0) for x in range(12) for y in range(12)]
        known = set(cells)
        edges = [
            (c, n)
            for c in cells
            for n in (
                (c[0] + 1, c[1], 0),
                (c[0] - 1, c[1], 0),
                (c[0], c[1] + 1, 0),
                (c[0], c[1] - 1, 0),
            )
            if n in known
        ]
        return prepare_geometry(dict(map_id=777, cells=cells, edges=edges))

    def test_prepared_sources_survive_cache_eviction_without_reload(self):
        geometry, surfaces, provenance = self.geometry(), object(), {"map_id": 777}
        terrain = PreparedTerrain("release-a", 777, geometry, surfaces, provenance)
        with ExitStack() as stack:
            prefix = "wakfu_server.combat.combat_terrain."
            stack.enter_context(
                patch(prefix + "protocol_catalog.release", return_value="release-a")
            )
            for name in (
                "published_geometry",
                "native_qi_surfaces",
                "native_qi_surface_provenance",
            ):
                stack.enter_context(
                    patch(prefix + name, side_effect=AssertionError("cold rebuild"))
                )
            indices = stack.enter_context(
                patch(prefix + "native_surface_indices", return_value={})
            )
            stack.enter_context(patch(prefix + "arena", return_value={}))
            selected = local_arena(
                777,
                1,
                (5, 5, 0),
                [(6, 5, 0)],
                variation_seed=42,
                prepared_terrain=terrain,
            )
        self.assertIs(indices.call_args.args[0], surfaces)
        self.assertIs(selected["native_qi_surface_provenance"], provenance)
        self.assertTrue(selected["validated_cells"] <= geometry.cells)

    def test_prepared_map_and_revision_are_revalidated(self):
        terrain = PreparedTerrain("release-a", 777, self.geometry(), object(), {})
        for map_id, revision in ((778, "release-a"), (777, "release-b")):
            with patch(
                "wakfu_server.combat.combat_terrain.protocol_catalog.release",
                return_value=revision,
            ), self.assertRaisesRegex(ValueError, "scope or catalog"):
                local_arena(map_id, 1, (5, 5, 0), [(6, 5, 0)], prepared_terrain=terrain)

    def test_preparation_retains_full_verified_sources_and_pins_revision(self):
        geometry, surfaces, provenance = self.geometry(), object(), {"map_id": 777}
        prefix = "wakfu_server.combat.combat_terrain."
        with patch(prefix + "published_geometry", return_value=geometry), patch(
            prefix + "native_qi_surfaces", return_value=surfaces
        ), patch(
            prefix + "native_qi_surface_provenance", return_value=provenance
        ), patch(
            prefix + "protocol_catalog.release", return_value="release-a"
        ):
            terrain = prepare_terrain(777)
            self.assertIs(terrain.geometry, geometry)
            self.assertIs(terrain.surfaces, surfaces)
            self.assertIs(terrain.provenance, provenance)
        with patch(prefix + "published_geometry", return_value=geometry), patch(
            prefix + "native_qi_surfaces", return_value=surfaces
        ), patch(
            prefix + "native_qi_surface_provenance", return_value=provenance
        ), patch(
            prefix + "protocol_catalog.release", side_effect=["release-a", "release-b"]
        ), self.assertRaisesRegex(
            ValueError, "revision changed"
        ):
            prepare_terrain(777)


if __name__ == "__main__":
    unittest.main()
