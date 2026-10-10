"""Deadline and parity coverage for complete graph identity traversal."""
import unittest
from wakfu_ai.context.native_graph_parts import _pack, _unpack, _terrain_ids, _remap
from wakfu_ai.native.native_deadline import bounded


class GraphPartsDeadlineTests(unittest.TestCase):
    def expires(self, operation):
        calls = 0

        def clock():
            nonlocal calls
            calls += 1
            return 0 if calls < 5 else 2

        with self.assertRaisesRegex(TimeoutError, "deadline"):
            with bounded(1, clock=clock):
                operation()
        self.assertEqual(calls, 5)

    def test_single_large_run_expires_during_expansion(self):
        self.expires(
            lambda: _unpack(
                {"count": 100000, "runs": [[0, 100000]]},
                bound=100000,
                maximum_count=100000,
            )
        )

    def test_pack_expires_during_iteration(self):
        self.expires(lambda: _pack(list(range(100000))))

    def test_remap_expires_inside_one_large_node(self):
        node = {"type": "tuple", "items": [{"ref": 0}] * 100000}
        self.expires(lambda: _remap(node, [3]))

    def test_terrain_traversal_expires_inside_one_large_node(self):
        node = {
            "type": "frozenset",
            "items": [{"ref": 1}] * 100000,
            "nativeClass": {
                "module": "wakfu_server.combat_geometry_snapshot",
                "name": "ImmutableTerrainSet",
            },
            "fields": {},
        }
        self.expires(lambda: _terrain_ids([node, {"type": "tuple", "items": []}], 0))

    def test_identity_roundtrip_and_remap_preserve_all_values(self):
        values = list(range(1000)) + [10, 9, 8] + list(range(2000, 4000))
        with bounded(float("inf")):
            packed = _pack(values)
            self.assertEqual(
                _unpack(packed, bound=4000, maximum_count=len(values)), values
            )
            node = {"type": "tuple", "items": [{"ref": 0}, {"value": 9}]}
            self.assertEqual(
                _remap(node, [12]),
                {"type": "tuple", "items": [{"ref": 12}, {"value": 9}]},
            )
        self.assertEqual(node["items"][0], {"ref": 0})
