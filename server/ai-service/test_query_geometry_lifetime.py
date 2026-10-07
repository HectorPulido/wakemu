"""Geometry decoding releases its full source graph without cyclic GC."""
import gc
import unittest
import weakref

from native_context import NativeGraph, encode
from query_search import _sequence


class QueryGeometryLifetimeTests(unittest.TestCase):
    def test_shared_memo_preserves_cell_and_edge_endpoint_aliases(self):
        start, end = tuple([0, 0, 0]), tuple([1, 0, 1])
        graph = NativeGraph(encode(dict(cells=[start, end], edges=[(start, end)])))
        memo = {}
        cells = _sequence(graph, graph.field(graph.data["root"], "cells"), memo)
        edges = _sequence(graph, graph.field(graph.data["root"], "edges"), memo)
        self.assertIs(edges[0][0], cells[0])
        self.assertIs(edges[0][1], cells[1])

    def test_shared_memo_cannot_confuse_different_graphs_or_equal_distinct_nodes(self):
        left, right = tuple([1, 2, 3]), tuple([1, 2, 3])
        graph = NativeGraph(encode([left, right]))
        other = NativeGraph(encode([(7, 8, 9)]))
        memo = {}
        decoded = _sequence(graph, graph.data["root"], memo)
        with self.assertRaisesRegex(ValueError, "different graph"):
            _sequence(other, other.data["root"], memo)
        different = _sequence(other, other.data["root"], {})
        self.assertEqual(decoded[0], decoded[1])
        self.assertIsNot(decoded[0], decoded[1])
        self.assertEqual(different, [(7, 8, 9)])

    def test_clearing_shared_memo_releases_source_without_cyclic_gc(self):
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            graph = NativeGraph(encode([(0, 0, 0)]))
            source = weakref.ref(graph)
            memo = {}
            decoded = _sequence(graph, graph.data["root"], memo)
            del graph
            self.assertIsNotNone(source())
            memo.clear()
            self.assertIsNone(source())
            self.assertEqual(decoded, [(0, 0, 0)])
        finally:
            if was_enabled:
                gc.enable()

    def test_successful_sequence_does_not_retain_source_graph(self):
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            graph = NativeGraph(encode([(0, 0, 0), (1, 0, 1)]))
            source = weakref.ref(graph)
            result = _sequence(graph, graph.data["root"])
            self.assertEqual(result, [(0, 0, 0), (1, 0, 1)])
            del graph
            self.assertIsNone(source())
        finally:
            if was_enabled:
                gc.enable()

    def test_rejected_cycle_does_not_retain_source_graph(self):
        def rejected_graph():
            graph = NativeGraph(
                dict(
                    encoding="wakfu-native-graph-1",
                    root={"ref": 0},
                    nodes=[
                        dict(type="list", items=[{"ref": 1}]),
                        dict(type="tuple", items=[{"ref": 1}]),
                    ],
                )
            )
            source = weakref.ref(graph)
            try:
                _sequence(graph, graph.data["root"])
            except ValueError as error:
                self.assertIn("Cyclic native value", str(error))
            else:
                self.fail("A cyclic tuple must require reference navigation")
            return source

        was_enabled = gc.isenabled()
        gc.disable()
        try:
            self.assertIsNone(rejected_graph()())
        finally:
            if was_enabled:
                gc.enable()
