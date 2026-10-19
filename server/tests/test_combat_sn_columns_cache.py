"""Published native Sn geometry is cached without retaining mutable QI state."""
import copy
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from threading import Lock
from time import sleep
import unittest
from unittest.mock import patch

import wakfu_server.combat_sn_path as combat_sn_path
from wakfu_server.combat_sn_path import NativeSnColumns
from wakfu_server.combat_microbot_path import microbot_path_projection
from wakfu_server.combat_qi_snapshot import NativeQISnapshot
from wakfu_server.combat_qi_surfaces import NativeQISurfaces


def published(map_id=1134, *, source_sha256="a" * 64):
    return {
        "schema": "native-Sn-Vy-columns-v1",
        "map_id": map_id,
        "source_sha256": source_sha256,
        "chunks": [
            {
                "x": 0,
                "y": 0,
                "width": 18,
                "height": 18,
                "columns": [[0, 0, [[0, 0, 0, 0, 0, False]]]],
            }
        ],
    }


class NativeSnColumnsCacheTests(unittest.TestCase):
    def setUp(self):
        combat_sn_path._published_columns.cache_clear()

    def tearDown(self):
        combat_sn_path._published_columns.cache_clear()

    def test_same_release_and_map_reuses_geometry_but_revision_or_map_does_not(self):
        calls = []

        def load(map_id):
            calls.append(map_id)
            return NativeSnColumns(
                published(map_id), map_id=map_id, source_sha256="a" * 64
            )

        with (
            patch.object(combat_sn_path.protocol_catalog, "release", return_value="r1"),
            patch.object(
                NativeSnColumns,
                "_load_published",
                classmethod(lambda cls, mid: load(mid)),
            ),
        ):
            first = NativeSnColumns.from_published(1134)
            self.assertIs(first, NativeSnColumns.from_published(1134))
            second_map = NativeSnColumns.from_published(1135)
            with patch.object(
                combat_sn_path.protocol_catalog, "release", return_value="r2"
            ):
                new_revision = NativeSnColumns.from_published(1134)

        self.assertEqual(calls, [1134, 1135, 1134])
        self.assertIsNot(first, second_map)
        self.assertIsNot(first, new_revision)

    def test_failed_cold_load_is_not_cached_and_retry_uses_verified_loader(self):
        calls = []

        def load(map_id):
            calls.append(map_id)
            if len(calls) == 1:
                raise ValueError("published map hash mismatch")
            return NativeSnColumns(
                published(map_id), map_id=map_id, source_sha256="a" * 64
            )

        with (
            patch.object(combat_sn_path.protocol_catalog, "release", return_value="r1"),
            patch.object(
                NativeSnColumns,
                "_load_published",
                classmethod(lambda cls, mid: load(mid)),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                NativeSnColumns.from_published(1134)
            recovered = NativeSnColumns.from_published(1134)
            self.assertIs(recovered, NativeSnColumns.from_published(1134))

        self.assertEqual(calls, [1134, 1134])

    def test_release_change_during_cold_load_rejects_uncertain_geometry(self):
        releases = iter(("r1", "r1", "r2"))
        calls = []

        def load(map_id):
            calls.append(map_id)
            return NativeSnColumns(
                published(map_id), map_id=map_id, source_sha256="a" * 64
            )

        with (
            patch.object(
                combat_sn_path.protocol_catalog,
                "release",
                side_effect=lambda: next(releases),
            ),
            patch.object(
                NativeSnColumns,
                "_load_published",
                classmethod(lambda cls, mid: load(mid)),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "revision changed during"):
                NativeSnColumns.from_published(1134)
            self.assertEqual(combat_sn_path._published_columns.cache_info().currsize, 0)

        self.assertEqual(calls, [1134])

    def test_concurrent_cold_requests_share_one_verified_map_load(self):
        calls = []
        calls_lock = Lock()

        def load(map_id):
            with calls_lock:
                calls.append(map_id)
            sleep(0.02)
            return NativeSnColumns(
                published(map_id), map_id=map_id, source_sha256="a" * 64
            )

        with (
            patch.object(combat_sn_path.protocol_catalog, "release", return_value="r1"),
            patch.object(
                NativeSnColumns,
                "_load_published",
                classmethod(lambda cls, mid: load(mid)),
            ),
        ):
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(
                    pool.map(lambda _: NativeSnColumns.from_published(1134), range(6))
                )

        self.assertEqual(calls, [1134])
        self.assertTrue(all(result is results[0] for result in results))

    def test_cache_capacity_is_bounded_and_evicted_geometry_can_reload(self):
        calls = []

        def load(map_id):
            calls.append(map_id)
            return NativeSnColumns(
                published(map_id), map_id=map_id, source_sha256="a" * 64
            )

        with (
            patch.object(combat_sn_path.protocol_catalog, "release", return_value="r1"),
            patch.object(
                NativeSnColumns,
                "_load_published",
                classmethod(lambda cls, mid: load(mid)),
            ),
        ):
            first = NativeSnColumns.from_published(1134)
            for map_id in (1135, 1136, 1137, 1138):
                NativeSnColumns.from_published(map_id)
            info = combat_sn_path._published_columns.cache_info()
            reloaded = NativeSnColumns.from_published(1134)

        self.assertEqual(info.maxsize, 4)
        self.assertEqual(info.currsize, 4)
        self.assertEqual(calls, [1134, 1135, 1136, 1137, 1138, 1134])
        self.assertIsNot(first, reloaded)

    def test_cached_geometry_is_deeply_immutable_and_does_not_alias_publication(self):
        data = published()
        columns = NativeSnColumns(data, map_id=1134, source_sha256="a" * 64)
        data["chunks"][0]["columns"][0][2][0][0] = 99
        self.assertEqual(columns.column(0, 0)[0].z, 0)
        self.assertIs(copy.deepcopy(columns), columns)
        with self.assertRaises(TypeError):
            columns.chunks[0][1][0, 0] = ()
        with self.assertRaises(AttributeError):
            columns.map_id = 999

    def test_incomplete_overlapping_or_wrong_provenance_publication_is_rejected(self):
        overlap = published()
        overlap["chunks"].append(
            {
                "x": 17,
                "y": 0,
                "width": 18,
                "height": 18,
                "columns": [],
            }
        )
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            NativeSnColumns(overlap, map_id=1134, source_sha256="a" * 64)
        with self.assertRaisesRegex(ValueError, "provenance"):
            NativeSnColumns(
                published(source_sha256="b" * 64), map_id=1134, source_sha256="a" * 64
            )
        with self.assertRaisesRegex(ValueError, "physical Vy field"):
            bad = published()
            bad["chunks"][0]["columns"][0][2][0][0] = 40000
            NativeSnColumns(bad, map_id=1134, source_sha256="a" * 64)

    def test_microbot_projection_reuses_geometry_but_takes_fresh_live_qi_snapshot(self):
        import wakfu_server.combat_qi_fight as combat_qi_fight
        import wakfu_server.combat_qi_surface_catalog as surface_catalog

        columns = NativeSnColumns(published(), map_id=1134, source_sha256="a" * 64)
        surfaces = NativeQISurfaces(
            {
                "schema": "native-QI-Vy-columns-v1",
                "map_id": 1134,
                "source_sha256": "b" * 64,
                "chunks": [
                    {
                        "x": 0,
                        "y": 0,
                        "width": 1,
                        "height": 1,
                        "columns": [[0, 0, [[3, 0], [9, 0]]]],
                    }
                ],
            },
            map_id=1134,
            source_sha256="b" * 64,
        )
        live = [
            NativeQISnapshot(
                {"x": 0, "y": 0, "width": 1, "height": 1, "cell_masks": [mask]},
                obstacles=[],
            )
            for mask in (0, 1)
        ]
        snapshots = iter(live)

        class Registry:
            def snapshot(self):
                return next(snapshots)

        fight = SimpleNamespace(native_qi_surface_provenance={"map_id": 1134})
        with (
            patch.object(
                combat_qi_fight,
                "current_registry",
                side_effect=lambda fight: Registry(),
            ),
            patch.object(
                surface_catalog,
                "native_qi_surface_provenance",
                return_value={"map_id": 1134},
            ),
            patch.object(surface_catalog, "native_qi_surfaces", return_value=surfaces),
            patch.object(
                NativeSnColumns, "from_published", return_value=columns
            ) as load_columns,
        ):
            first = microbot_path_projection(fight)
            second = microbot_path_projection(fight)

        self.assertIs(first.columns, second.columns)
        self.assertIsNot(first.qi, second.qi)
        self.assertEqual((first.surface_z(0, 0), second.surface_z(0, 0)), (3, 9))
        self.assertEqual(load_columns.call_count, 2)


if __name__ == "__main__":
    unittest.main()
