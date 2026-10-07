"""Complete native graphs retain the exact bytes across cached terrain splices."""
import json
import unittest
from unittest.mock import patch

from native_context import _encode, encode_bytes
import native_geometry_fragments
from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet


class NativeGeometryIntegrationTests(unittest.TestCase):
    def test_encoder_uses_verified_fragment_on_cold_and_warm_calls(self):
        terrain = ImmutableTerrainSet([(0, 0, 0), (1, 0, 1)])
        used = []
        original = native_geometry_fragments.get_fragment

        def observed(*args, **kwargs):
            fragment = original(*args, **kwargs)
            used.append(fragment)
            return fragment

        with patch.object(native_geometry_fragments, "get_fragment", observed):
            self.assert_complete_bytes(dict(terrain=terrain))
        self.assertEqual(len(used), 2)
        self.assertIsNone(used[0])
        self.assertIsNotNone(used[1])

    def assert_complete_bytes(self, value):
        baseline = _encode(value, serialize_nodes=True, _geometry_cache=False)
        self.assertEqual(encode_bytes(value), baseline)
        self.assertEqual(encode_bytes(value), baseline)
        return json.loads(baseline)

    def test_shared_geometry_and_external_endpoint_aliases(self):
        start = tuple([1, 2, 3])
        equal_start = tuple([1, 2, 3])
        end = tuple([2, 2, 3])
        edge = (start, end)
        cells = ImmutableTerrainSet([start, end])
        edges = ImmutableTerrainSet([edge, (equal_start, start)])
        value = dict(
            actor=start,
            existing_edge=edge,
            cells=cells,
            edges=edges,
            repeated=edges,
            equal_coordinate=equal_start,
        )
        self.assert_complete_bytes(value)

    def test_terrain_inside_cyclic_full_context(self):
        terrain = ImmutableTerrainSet([(0, 0, 0), (1, 0, 1)])
        value = dict(terrain=terrain, future_private=b"complete")
        value["cycle"] = value
        value["list"] = [value, terrain]
        self.assert_complete_bytes(value)

    def test_future_fields_and_subclasses_use_complete_encoder(self):
        class FutureTerrain(ImmutableTerrainSet):
            pass

        terrain = FutureTerrain([(0, 0, 0)])
        terrain.future = {"unrecognized": [1, 2, 3]}
        graph = self.assert_complete_bytes(dict(terrain=terrain))
        self.assertTrue(
            any("future" in node.get("fields", {}) for node in graph["nodes"])
        )

    def test_plain_frozen_and_custom_coordinate_values_preserved(self):
        class Coordinate(tuple):
            pass

        terrain = ImmutableTerrainSet([Coordinate((1, 2, 3))])
        self.assert_complete_bytes(dict(plain=frozenset([3, 1]), terrain=terrain))

    def test_future_tuple_with_mutable_children_preserves_complete_graph(self):
        mutable = [1, {"future": [2, 3]}]
        value = (mutable, {"shared": mutable}, (mutable,))
        mutable.append(value)
        self.assert_complete_bytes(value)

    def test_future_tuple_does_not_invoke_custom_hash(self):
        class FutureValue:
            def __hash__(self):
                raise AssertionError(
                    "Encoder must preserve fields without hashing this value"
                )

        child = FutureValue()
        child.payload = {"complete": [1, 2]}
        self.assert_complete_bytes((child, child))
