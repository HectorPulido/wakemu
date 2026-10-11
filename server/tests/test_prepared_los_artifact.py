"""Small fixtures for source-bound prepared native LOS columns."""
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.prepared_geometry import ArtifactUnavailable
from wakfu_server import prepared_los
from wakfu_server.combat import combat_native_los_ray as native_ray


class PreparedLosArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = {
            "schema": "native-Sf-Vz-columns-v1",
            "map_id": 527,
            "columns": [
                [0, 0, [[10, 2, True], [20, 3, False]]],
                [1, 0, [[10, 30, True]]],
                [0, 0, [[20, 30, True], [10, 30, True]]],
                [2, 0, [[10, 30, True]]],
            ],
        }
        self.source_raw = json.dumps(self.source).encode()
        self.digest = hashlib.sha256(self.source_raw).hexdigest()
        self.revision = "los-fixture-r1"

    def build(self):
        return prepared_los.build_artifact(
            self.directory,
            map_id=527,
            revision=self.revision,
            source_raw=self.source_raw,
        )

    def clear_caches(self):
        prepared_los._inventory.cache_clear()
        prepared_los._published.cache_clear()
        native_ray.topology_columns.cache_clear()
        native_ray.static_ray.cache_clear()

    def load_cli(self):
        tools_dir = str(Path(__file__).resolve().parents[1] / "tools")
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
            self.addCleanup(sys.path.remove, tools_dir)
        path = Path(tools_dir) / "prepare_los_artifacts.py"
        spec = importlib.util.spec_from_file_location(
            "prepare_los_artifacts_test", path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_build_preserves_column_overwrite_order_and_surface_order(self):
        columns = self.build()
        self.assertEqual(list(columns), [(0, 0), (1, 0), (2, 0)])
        self.assertEqual(columns[(0, 0)], ((20, 30, True), (10, 30, True)))
        self.assertEqual(columns[(1, 0)], ((10, 30, True),))
        with self.assertRaises(TypeError):
            columns[(3, 0)] = ()
        with self.assertRaises(TypeError):
            columns[(0, 0)][0] = (0, 0, False)

    def test_missing_stale_revision_map_and_source_hash_are_unavailable(self):
        with self.assertRaises(ArtifactUnavailable):
            prepared_los.load_artifact(
                self.directory,
                map_id=527,
                revision=self.revision,
                source_sha256=self.digest,
            )
        self.build()
        for kwargs in (
            dict(map_id=527, revision="old", source_sha256=self.digest),
            dict(map_id=528, revision=self.revision, source_sha256=self.digest),
            dict(map_id=527, revision=self.revision, source_sha256="0" * 64),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ArtifactUnavailable):
                prepared_los.load_artifact(self.directory, **kwargs)

    def test_corruption_is_unavailable_and_topology_hook_falls_back_to_source(self):
        self.build()
        binary = next(self.directory.rglob("*.marshal"))
        original = binary.read_bytes()
        binary.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        kwargs = dict(map_id=527, revision=self.revision, source_sha256=self.digest)
        with self.assertRaises(ArtifactUnavailable):
            prepared_los.load_artifact(self.directory, **kwargs)

        from wakfu_server import native_catalog

        self.clear_caches()
        inventory = {"native-los-topology/527.json": self.digest}
        with patch.dict(
            "os.environ", {"WAKFU_PREPARED_LOS_DIR": str(self.directory)}
        ), patch.object(
            native_catalog, "release", return_value=self.revision
        ), patch.object(
            native_catalog, "document_hashes", return_value=inventory
        ), patch.object(
            native_catalog, "exists", return_value=True
        ), patch.object(
            native_catalog, "load", return_value=self.source
        ) as load:
            result = native_ray.topology_columns(527)
        self.assertEqual(
            list(result.items()),
            list(native_ray.prepare_columns(self.source, 527).items()),
        )
        self.assertEqual(load.call_count, 1)

    def test_published_columns_cache_is_revision_scoped_and_hook_output_is_immutable(
        self,
    ):
        expected = self.build()
        from wakfu_server import native_catalog

        self.clear_caches()
        inventory = {"native-los-topology/527.json": self.digest}
        with patch.dict(
            "os.environ", {"WAKFU_PREPARED_LOS_DIR": str(self.directory)}
        ), patch.object(
            native_catalog, "release", return_value=self.revision
        ), patch.object(
            native_catalog, "document_hashes", return_value=inventory
        ):
            result = native_ray.topology_columns(527)
            self.assertEqual(list(result.items()), list(expected.items()))
            with self.assertRaises(TypeError):
                result[(9, 9)] = ()
        native_ray.topology_columns.cache_clear()
        self.clear_caches()
        with patch.dict(
            "os.environ", {"WAKFU_PREPARED_LOS_DIR": str(self.directory)}
        ), patch.object(native_catalog, "release", return_value="new-r"), patch.object(
            native_catalog, "document_hashes", return_value=inventory
        ), patch.object(
            native_catalog, "exists", return_value=False
        ), self.assertRaises(
            ValueError
        ):
            native_ray.topology_columns(527)

    def test_static_ray_matches_source_columns_and_live_actor_blockers_remain_live(
        self,
    ):
        self.build()
        from wakfu_server import native_catalog
        from wakfu_server.combat.combat_los import authoritative_visible

        self.clear_caches()
        inventory = {"native-los-topology/527.json": self.digest}
        program = (
            ("aload", 0),
            ("aload", 0),
            ("getfield", "bnO"),
            ("putfield", "bnU"),
            ("aload", 0),
            ("aload", 0),
            ("getfield", "bnP"),
            ("putfield", "bnV"),
            ("aload", 0),
            ("aload", 0),
            ("getfield", "bnQ"),
            ("putfield", "bnW"),
            ("aload", 0),
            ("aload", 0),
            ("getfield", "bnT"),
            ("putfield", "bnX"),
            ("aload", 0),
            ("constant", 0),
            ("constant", 0),
            ("constant", 0),
            ("invokevirtual", "m"),
            ("istore", 1),
            ("aload", 0),
            ("constant", 1),
            ("constant", 0),
            ("constant", 0),
            ("invokevirtual", "m"),
            ("istore", 1),
            ("aload", 0),
            ("constant", 2),
            ("constant", 0),
            ("constant", 0),
            ("invokevirtual", "m"),
            ("ireturn",),
        )
        with patch.dict(
            "os.environ", {"WAKFU_PREPARED_LOS_DIR": str(self.directory)}
        ), patch.object(
            native_catalog, "release", return_value=self.revision
        ), patch.object(
            native_catalog, "document_hashes", return_value=inventory
        ), patch.object(
            native_catalog, "exists", return_value=True
        ), patch.object(
            native_ray, "ray_program", return_value=program
        ):
            raw_columns = native_ray.prepare_columns(self.source, 527)
            with patch.object(native_ray, "topology_columns", return_value=raw_columns):
                expected = native_ray.static_ray(527, (0, 0, 0), (2, 0, 0))
            native_ray.static_ray.cache_clear()
            native_ray.topology_columns.cache_clear()
            actual = native_ray.static_ray(527, (0, 0, 0), (2, 0, 0))
            self.assertEqual(actual, expected)
            self.assertEqual(actual, (True, frozenset({(1, 0)})))

            actors = {
                1: SimpleNamespace(
                    id=1,
                    hp=100,
                    position=(0, 0, 0),
                    native_los_height=0,
                    native_obstacle_id=1,
                ),
                2: SimpleNamespace(
                    id=2,
                    hp=100,
                    position=(2, 0, 0),
                    native_los_height=0,
                    native_obstacle_id=2,
                ),
                3: SimpleNamespace(
                    id=3,
                    hp=100,
                    position=(1, 0, 0),
                    native_los_height=0,
                    native_obstacle_id=3,
                ),
            }
            fight = SimpleNamespace(
                actors=actors, walkable={(x, 0, 0) for x in range(3)}
            )
            blockers = {1: [], 2: [], 3: [(1, 0)]}
            self.assertFalse(
                authoritative_visible(
                    527, (0, 0, 0), (2, 0, 0), fight, blocking_footprints=blockers
                )
            )
            blockers[3] = []
            self.assertTrue(
                authoritative_visible(
                    527, (0, 0, 0), (2, 0, 0), fight, blocking_footprints=blockers
                )
            )

    def test_worker_reuses_matching_artifact_without_rewriting(self):
        self.build()
        cli = self.load_cli()
        from wakfu_server import native_catalog
        import prepare_geometry_artifacts
        from unittest.mock import patch

        binary, manifest = next(self.directory.rglob("*.marshal")), next(
            self.directory.rglob("*.json")
        )
        before = {
            path: (path.stat().st_mtime_ns, path.read_bytes())
            for path in (binary, manifest)
        }
        inventory = {"native-los-topology/527.json": self.digest}
        output = io.StringIO()
        with patch.object(
            sys,
            "argv",
            [
                "prepare_los_artifacts.py",
                "--worker",
                "--map",
                "527",
                "--output",
                str(self.directory),
            ],
        ), patch.object(
            native_catalog, "release", return_value=self.revision
        ), patch.object(
            native_catalog, "document_hashes", return_value=inventory
        ), patch.object(
            native_catalog, "read_bytes", return_value=self.source_raw
        ), patch.object(
            cli, "build_artifact", side_effect=AssertionError("reuse expected")
        ), patch.object(
            cli, "run_isolated", side_effect=AssertionError("worker only")
        ), patch.object(
            prepare_geometry_artifacts,
            "build_artifact",
            side_effect=AssertionError("geometry builder must stay unused"),
        ), patch.object(
            prepare_geometry_artifacts,
            "prepare_geometry",
            side_effect=AssertionError("geometry parser must stay unused"),
        ), redirect_stdout(
            output
        ):
            cli.main()
        self.assertIn('"reused": true', output.getvalue())
        for path, (mtime, data) in before.items():
            self.assertEqual(path.stat().st_mtime_ns, mtime)
            self.assertEqual(path.read_bytes(), data)

    def test_worker_repairs_corrupt_los_artifact_without_geometry_build(self):
        self.build()
        cli = self.load_cli()
        from wakfu_server import native_catalog
        import prepare_geometry_artifacts
        from unittest.mock import patch

        binary = next(self.directory.rglob("*.marshal"))
        corrupted = binary.read_bytes()
        binary.write_bytes(corrupted[:-1] + bytes([corrupted[-1] ^ 1]))
        inventory = {"native-los-topology/527.json": self.digest}
        output = io.StringIO()
        with patch.object(
            sys,
            "argv",
            [
                "prepare_los_artifacts.py",
                "--worker",
                "--map",
                "527",
                "--output",
                str(self.directory),
            ],
        ), patch.object(
            native_catalog, "release", return_value=self.revision
        ), patch.object(
            native_catalog, "document_hashes", return_value=inventory
        ), patch.object(
            native_catalog, "read_bytes", return_value=self.source_raw
        ), patch.object(
            cli, "build_artifact", wraps=prepared_los.build_artifact
        ) as los_build, patch.object(
            cli, "run_isolated", side_effect=AssertionError("worker only")
        ), patch.object(
            prepare_geometry_artifacts,
            "build_artifact",
            side_effect=AssertionError("geometry builder must stay unused"),
        ), patch.object(
            prepare_geometry_artifacts,
            "prepare_geometry",
            side_effect=AssertionError("geometry parser must stay unused"),
        ), redirect_stdout(
            output
        ):
            cli.main()
        los_build.assert_called_once_with(
            self.directory,
            map_id=527,
            revision=self.revision,
            source_raw=self.source_raw,
        )
        self.assertIn('"reused": false', output.getvalue())
        loaded = prepared_los.load_artifact(
            self.directory,
            map_id=527,
            revision=self.revision,
            source_sha256=self.digest,
        )
        self.assertEqual(
            list(loaded.items()),
            list(native_ray.prepare_columns(self.source, 527).items()),
        )


if __name__ == "__main__":
    unittest.main()
