"""Graph traversal deadlines include primitives and memoized references."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_ai.context.native_context import encode, encode_bytes, NativeGraph
from wakfu_ai.native.native_deadline import bounded


class TraversalDeadlineTests(unittest.TestCase):
    def expire_during_traversal(self, value, encoder):
        calls = 0

        def clock():
            nonlocal calls
            calls += 1
            return 0 if calls <= 4 else 2

        with self.assertRaisesRegex(TimeoutError, "deadline"):
            with bounded(1, clock=clock):
                encoder(value)
        self.assertEqual(calls, 5)

    def test_large_primitive_sequence_checks_deadline(self):
        for encoder in (encode, encode_bytes):
            with self.subTest(encoder=encoder.__name__):
                self.expire_during_traversal(list(range(100000)), encoder)

    def test_large_alias_sequence_checks_deadline(self):
        shared = {"authority": 1}
        for encoder in (encode, encode_bytes):
            with self.subTest(encoder=encoder.__name__):
                self.expire_during_traversal([shared] * 100000, encoder)

    def test_single_node_validation_checks_primitive_references(self):
        encoded = encode(list(range(100000)))
        self.expire_during_traversal(encoded, NativeGraph)

    def test_plain_projection_checks_primitive_references(self):
        graph = NativeGraph(encode(list(range(100000))))
        self.expire_during_traversal(graph.data["root"], graph.plain)

    def test_deadline_checks_do_not_change_complete_graph_or_aliases(self):
        shared = {"levels": list(range(1500))}
        value = {"owned": [shared, shared], "primitives": list(range(2000))}
        ordinary = encode(value)
        with bounded(float("inf")):
            self.assertEqual(encode(value), ordinary)
            self.assertEqual(json.loads(encode_bytes(value)), ordinary)
        graph = NativeGraph(ordinary)
        owned = graph.field(ordinary["root"], "owned")
        items = graph.resolve(owned)["items"]
        self.assertEqual(items[0], items[1])
        self.assertEqual(graph.plain(owned), [shared, shared])


if __name__ == "__main__":
    unittest.main()
