"""Validated geometry reuse must not change directed native topology."""
import unittest
from unittest.mock import patch

from wakfu_server.combat_geometry import (
    prepare_geometry,
    published_geometry,
    _published_geometry,
    reachable,
    edges_within,
)
from wakfu_server.combat_arena_selection import (
    _reachable,
    compact_encounter,
    bounded_arena,
)


class PreparedGeometryTests(unittest.TestCase):
    def geometry(self):
        cells = [[0, 0, 0], [1, 0, 2], [2, 0, 4], [3, 0, 4]]
        edges = [[a, b] for a, b in zip(cells, cells[1:])]
        edges += [[b, a] for a, b in edges]
        return dict(map_id=777, cells=cells, edges=edges)

    def test_mutable_inputs_are_snapshotted_and_revalidated(self):
        raw = self.geometry()
        first = prepare_geometry(raw)
        raw["cells"][0][2] = 7
        self.assertIn((0, 0, 0), first.cells)
        self.assertNotIn((0, 0, 7), first.cells)
        # Edges reference the same raw lists, so the mutated export is valid
        # but must not reuse the original snapshot by dictionary identity.
        second = prepare_geometry(raw)
        self.assertIn((0, 0, 7), second.cells)
        raw["edges"].append([[99, 0, 0], [100, 0, 0]])
        with self.assertRaises(ValueError):
            prepare_geometry(raw)

    def test_prepared_values_and_adjacency_cannot_be_mutated(self):
        geometry = prepare_geometry(self.geometry())
        self.assertIs(prepare_geometry(geometry), geometry)
        with self.assertRaises(AttributeError):
            geometry.cells.add((9, 0, 0))
        with self.assertRaises(TypeError):
            geometry.outgoing[(0, 0, 0)] = ()
        with self.assertRaises(AttributeError):
            geometry.map_id = 999

    def test_induced_reachability_matches_original_graph_walk(self):
        raw = self.geometry()
        geometry = prepare_geometry(raw)
        origin = (0, 0, 0)
        for cells in (geometry.cells, {(0, 0, 0), (1, 0, 2), (3, 0, 4)}):
            self.assertEqual(
                reachable(origin, cells, geometry.outgoing),
                _reachable(origin, cells, geometry.edges),
            )
            self.assertEqual(
                edges_within(cells, geometry.outgoing),
                {(a, b) for a, b in geometry.edges if a in cells and b in cells},
            )

    def test_prepared_and_mutable_selection_results_match(self):
        raw = self.geometry()
        geometry = prepare_geometry(raw)
        for selector in (bounded_arena, compact_encounter):
            with self.subTest(selector=selector.__name__):
                self.assertEqual(
                    selector(raw, (0, 0, 0), [(3, 0, 4)]),
                    selector(geometry, (0, 0, 0), [(3, 0, 4)]),
                )

    def test_published_cache_is_revision_scoped_and_detaches_source(self):
        raw = self.geometry()
        _published_geometry.cache_clear()
        self.addCleanup(_published_geometry.cache_clear)
        with patch(
            "wakfu_server.combat_geometry.protocol_catalog.release", return_value="r1"
        ) as release, patch(
            "wakfu_server.combat_geometry.protocol_catalog.exists", return_value=True
        ), patch(
            "wakfu_server.combat_geometry.protocol_catalog.load", return_value=raw
        ) as load:
            first = published_geometry(777)
            raw["cells"][0][2] = 7
            self.assertIs(published_geometry(777), first)
            self.assertEqual(load.call_count, 1)
            release.return_value = "r2"
            second = published_geometry(777)
            self.assertIn((0, 0, 7), second.cells)
            self.assertIn((0, 0, 0), first.cells)
            self.assertEqual(load.call_count, 2)
