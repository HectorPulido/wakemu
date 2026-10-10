import hashlib
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from wakfu_server.combat_qi_snapshot import NativeQISnapshot
from wakfu_server.combat_qi_surface_catalog import (
    _publication,
    native_qi_surfaces,
)
from wakfu_server.combat_geometry import _published_geometry
from wakfu_server.combat_terrain import local_arena, map_geometry


class TerrainSurfaceIntegrationTests(unittest.TestCase):
    def clear(self):
        _publication.cache_clear()
        native_qi_surfaces.cache_clear()
        map_geometry.cache_clear()
        _published_geometry.cache_clear()

    def fixture_catalog(self, root):
        """Patch the read-only published-catalog boundary to fixture files."""
        stack = ExitStack()
        stack.enter_context(patch("wakfu_server.combat_geometry.DATA_ROOT", root))
        stack.enter_context(patch("wakfu_server.combat_terrain.DATA_ROOT", root))
        stack.enter_context(
            patch("wakfu_server.combat_qi_surface_catalog.DATA_ROOT", root)
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_geometry.protocol_catalog.release",
                return_value="fixture",
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_geometry.protocol_catalog.exists",
                side_effect=lambda path: Path(path).is_file(),
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_geometry.protocol_catalog.load",
                side_effect=lambda path: json.loads(Path(path).read_bytes()),
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_geometry.protocol_catalog.read_bytes",
                side_effect=lambda path: Path(path).read_bytes(),
            )
        )
        return stack

    def fixture(self, root, *, tamper=None):
        directory = root / "native-qi-surfaces"
        directory.mkdir()
        geometry_directory = root / "combat-maps"
        geometry_directory.mkdir()
        rows = []
        for identity, z in ((9001, 19), (9002, -3)):
            cells = [[0, 0, z], [1, 0, z]]
            geometry = {
                "map_id": identity,
                "cells": cells,
                "edges": [[cells[0], cells[1]], [cells[1], cells[0]]],
            }
            (geometry_directory / f"{identity}.json").write_text(json.dumps(geometry))
            source_hash = hashlib.sha256(str(identity).encode()).hexdigest()
            data = {
                "schema": "native-QI-Vy-columns-v1",
                "map_id": identity,
                "source_sha256": source_hash,
                "chunks": [
                    {
                        "x": 0,
                        "y": 0,
                        "width": 2,
                        "height": 1,
                        "columns": [[x, 0, [[z - 1, -1], [z, 0]]] for x in (0, 1)],
                    }
                ],
            }
            if tamper == "source":
                data["source_sha256"] = "b" * 64
            raw = json.dumps(data).encode()
            path = directory / f"{identity}.json"
            path.write_bytes(raw)
            rows.append(
                {
                    "map_id": identity,
                    "status": "exported",
                    "source_sha256": source_hash,
                    "output_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
            if tamper == "output":
                path.write_bytes(raw + b"changed")
        rows.append({"map": "9003.jar", "status": "error"})
        (geometry_directory / "9003.json").write_text(
            json.dumps(
                {
                    "map_id": 9003,
                    "cells": [[0, 0, 0], [1, 0, 0]],
                    "edges": [[[0, 0, 0], [1, 0, 0]], [[1, 0, 0], [0, 0, 0]]],
                }
            )
        )
        manifest = json.dumps({"maps": rows}).encode()
        (directory / "manifest.json").write_bytes(manifest)
        publication = {
            "schema": "native-QI-surface-publication-v1",
            "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
            "counts": {"imported": 2, "failed_native": 1},
        }
        (directory / "publication.json").write_text(json.dumps(publication))

    def test_two_map_catalog_provenance_and_cached_immutable_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            self.clear()
            try:
                with self.fixture_catalog(root):
                    for identity, z in ((9001, 19), (9002, -3)):
                        first = local_arena(identity, 7, (0, 0, z), (1, 0, z))
                        second = local_arena(identity, 8, (0, 0, z), (1, 0, z))
                        # On this tiny map both native border cells are actor
                        # seeds, so the displayed perimeter is suppressed there.
                        self.assertEqual(first["cell_masks"], [1, 1])
                        self.assertEqual(
                            [mask & 63 for mask in first["cell_masks"]], [1, 1]
                        )
                        self.assertEqual(
                            first["native_qi_surface_provenance"],
                            second["native_qi_surface_provenance"],
                        )
                        self.assertEqual(
                            first["native_qi_surface_provenance"]["map_id"], identity
                        )
                        qi = NativeQISnapshot(first)
                        self.assertTrue(native_qi_surfaces(identity).j(qi, 0, 0, z))
                    with self.assertRaisesRegex(ValueError, "decoding failed"):
                        local_arena(9003, 7, (0, 0, 0), (1, 0, 0))
            finally:
                self.clear()

    def test_native_source_and_output_hash_mismatches_reject(self):
        for tamper, message in (("source", "provenance"), ("output", "checksum")):
            with self.subTest(
                tamper=tamper
            ), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.fixture(root, tamper=tamper)
                self.clear()
                try:
                    with self.fixture_catalog(root):
                        with self.assertRaisesRegex(ValueError, message):
                            local_arena(9001, 7, (0, 0, 19), (1, 0, 19))
                finally:
                    self.clear()

    def test_real_map_nonzero_floor_matches_all_selected_surfaces(self):
        with patch.dict("os.environ", {"WAKFU_COMBAT_ARENA_RADIUS": "12"}):
            result = local_arena(1134, 7, (61, -128, 50), (61, -129, 50))
        qi = NativeQISnapshot(result)
        surfaces = native_qi_surfaces(1134)
        self.assertTrue(any(mask & 63 for mask in qi.masks))
        for cell in result["validated_cells"]:
            self.assertIsNotNone(surfaces.i(qi, *cell))
            self.assertTrue(surfaces.j(qi, *cell))
        self.assertEqual(result["native_qi_surface_provenance"]["map_id"], 1134)


if __name__ == "__main__":
    unittest.main()
