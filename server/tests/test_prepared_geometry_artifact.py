"""Checksummed prepared geometry remains equivalent to native source data."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wakfu_server.storage.prepared_geometry import (
    ArtifactUnavailable,
    build_artifact,
    load_artifact,
)
from wakfu_server.combat_geometry import prepare_geometry
from wakfu_server.combat_forced_terrain import prepare_compact_index


class PreparedGeometryArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        cells = [[0, 0, 0], [1, 0, 2], [2, 0, 4], [2, 1, 4]]
        edges = [[cells[i], cells[i + 1]] for i in range(3)]
        edges += [[end, start] for start, end in edges]
        self.geometry_raw = json.dumps(
            {"map_id": 527, "cells": cells, "edges": edges}
        ).encode()
        self.forced_raw = json.dumps(
            {
                "schema_version": 1,
                "map_id": 527,
                "radius": 0,
                "jump": 4,
                "heights": [1, 25],
                "rows": [[0, 0, 0, 1, 0, [[(1 << 25) - 1, 2]]]],
            }
        ).encode()
        self.geometry_hash = hashlib.sha256(self.geometry_raw).hexdigest()
        self.forced_hash = hashlib.sha256(self.forced_raw).hexdigest()

    def build(self, *, forced=True):
        return build_artifact(
            self.directory,
            map_id=527,
            revision="r-test",
            geometry_raw=self.geometry_raw,
            forced_raw=self.forced_raw if forced else None,
        )

    def test_build_matches_source_geometry_and_forced_index_and_is_immutable(self):
        artifact = self.build()
        source = prepare_geometry(json.loads(self.geometry_raw))
        source_forced = prepare_compact_index(json.loads(self.forced_raw), 527, 0, 4)
        self.assertEqual(artifact.geometry, source)
        self.assertEqual(dict(artifact.forced_index), dict(source_forced))
        self.assertEqual(
            artifact.scope, (1, "r-test", 527, self.geometry_hash, self.forced_hash)
        )
        with self.assertRaises(AttributeError):
            artifact.geometry.cells.add((10, 10, 0))
        with self.assertRaises(TypeError):
            artifact.geometry.outgoing[(0, 0, 0)] = ()
        with self.assertRaises(TypeError):
            artifact.forced_index[((0, 0, 0), (1, 0))] = ()

    def test_missing_stale_identity_and_source_hash_are_unavailable(self):
        self.build()
        cases = (
            dict(
                map_id=528,
                revision="r-test",
                geometry_sha256=self.geometry_hash,
                forced_sha256=self.forced_hash,
            ),
            dict(
                map_id=527,
                revision="old-release",
                geometry_sha256=self.geometry_hash,
                forced_sha256=self.forced_hash,
            ),
            dict(
                map_id=527,
                revision="r-test",
                geometry_sha256="0" * 64,
                forced_sha256=self.forced_hash,
            ),
            dict(
                map_id=527,
                revision="r-test",
                geometry_sha256=self.geometry_hash,
                forced_sha256="1" * 64,
            ),
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ArtifactUnavailable):
                load_artifact(self.directory, **kwargs)
        with self.assertRaises(ArtifactUnavailable):
            load_artifact(
                self.directory,
                map_id=527,
                revision="r-test",
                geometry_sha256=self.geometry_hash,
            )

    def test_corrupt_binary_and_manifest_are_unavailable(self):
        self.build()
        artifact_path = next(self.directory.rglob("*.marshal"))
        manifest_path = next(self.directory.rglob("*.json"))
        kwargs = dict(
            map_id=527,
            revision="r-test",
            geometry_sha256=self.geometry_hash,
            forced_sha256=self.forced_hash,
        )
        binary = artifact_path.read_bytes()
        artifact_path.write_bytes(binary[:-1] + bytes([binary[-1] ^ 0xFF]))
        with self.assertRaises(ArtifactUnavailable):
            load_artifact(self.directory, **kwargs)
        artifact_path.write_bytes(binary)
        manifest = json.loads(manifest_path.read_bytes())
        manifest["scope"][2] = 528
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(ArtifactUnavailable):
            load_artifact(self.directory, **kwargs)

    def test_builder_rejects_invalid_identity_geometry_and_forced_source(self):
        with self.assertRaises(ValueError):
            build_artifact(
                self.directory,
                map_id=528,
                revision="r-test",
                geometry_raw=self.geometry_raw,
            )
        with self.assertRaises((ValueError, TypeError, json.JSONDecodeError)):
            build_artifact(
                self.directory, map_id=527, revision="r-test", geometry_raw=b"not-json"
            )
        malformed = json.dumps(
            {"map_id": 527, "cells": [[0, 0, 0]], "edges": [[[0, 0, 0], [8, 0, 0]]]}
        ).encode()
        with self.assertRaises(ValueError):
            build_artifact(
                self.directory, map_id=527, revision="r-test", geometry_raw=malformed
            )
        bad_forced = json.dumps(
            {
                "schema_version": 1,
                "map_id": 527,
                "radius": 0,
                "jump": 4,
                "heights": [1, 25],
                "rows": [[0, 0, 0, 1, 0, [[1, 2]]]],
            }
        ).encode()
        with self.assertRaises(ValueError):
            build_artifact(
                self.directory,
                map_id=527,
                revision="r-test",
                geometry_raw=self.geometry_raw,
                forced_raw=bad_forced,
            )

    def test_geometry_only_artifact_has_no_forced_index(self):
        artifact = self.build(forced=False)
        self.assertIsNone(artifact.forced_index)
        loaded = load_artifact(
            self.directory,
            map_id=527,
            revision="r-test",
            geometry_sha256=self.geometry_hash,
        )
        self.assertEqual(loaded.geometry, artifact.geometry)

    def test_published_artifact_cache_is_partitioned_by_native_revision(self):
        self.build(forced=False)
        from wakfu_server.storage import prepared_geometry
        from wakfu_server import native_catalog

        prepared_geometry._inventory.cache_clear()
        prepared_geometry._published.cache_clear()
        self.addCleanup(prepared_geometry._inventory.cache_clear)
        self.addCleanup(prepared_geometry._published.cache_clear)
        inventory = {"combat-maps/527.json": self.geometry_hash}
        with patch.dict(
            "os.environ", {"WAKFU_PREPARED_GEOMETRY_DIR": str(self.directory)}
        ), patch.object(native_catalog, "release", return_value="r-test"), patch.object(
            native_catalog, "document_hashes", return_value=inventory
        ):
            self.assertIsNotNone(prepared_geometry.published_artifact(527))
        with patch.dict(
            "os.environ", {"WAKFU_PREPARED_GEOMETRY_DIR": str(self.directory)}
        ), patch.object(
            native_catalog, "release", return_value="new-release"
        ), patch.object(
            native_catalog, "document_hashes", return_value=inventory
        ):
            self.assertIsNone(prepared_geometry.published_artifact(527))

    def test_runtime_geometry_and_forced_hooks_consume_the_published_artifact(self):
        artifact = self.build()
        from wakfu_server import native_catalog
        from wakfu_server.combat import combat_geometry, combat_forced_terrain
        from wakfu_server import prepared_geometry

        prepared_geometry._inventory.cache_clear()
        prepared_geometry._published.cache_clear()
        combat_geometry._published_geometry.cache_clear()
        combat_forced_terrain.compact_index.cache_clear()
        self.addCleanup(prepared_geometry._inventory.cache_clear)
        self.addCleanup(prepared_geometry._published.cache_clear)
        self.addCleanup(combat_geometry._published_geometry.cache_clear)
        self.addCleanup(combat_forced_terrain.compact_index.cache_clear)
        inventory = {
            "combat-maps/527.json": self.geometry_hash,
            "forced-transitions/527.json": self.forced_hash,
        }
        with patch.dict(
            "os.environ", {"WAKFU_PREPARED_GEOMETRY_DIR": str(self.directory)}
        ), patch.object(native_catalog, "release", return_value="r-test"), patch.object(
            native_catalog, "document_hashes", return_value=inventory
        ):
            self.assertEqual(combat_geometry.published_geometry(527), artifact.geometry)
            self.assertEqual(
                dict(combat_forced_terrain.compact_index(527, 0, 4)),
                dict(artifact.forced_index),
            )


if __name__ == "__main__":
    unittest.main()
