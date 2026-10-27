"""Rendered geometry may be reused only for complete current identity maps."""
import unittest
from unittest.mock import patch

from wakfu_ai.context import native_geometry_render_cache as cache
from wakfu_ai.context.native_context import _encode, _instance_fields, encode_bytes
from wakfu_ai.context.native_geometry_fragments import get_fragment, _NodeTemplate
from wakfu_ai.native.native_deadline import bounded
from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet


class NativeGeometryRenderCacheTests(unittest.TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def fragment(self, terrain):
        return get_fragment(
            terrain,
            lambda value: _encode(value, serialize_nodes=True, _geometry_cache=False),
            _instance_fields,
        )

    def assert_complete(self, value):
        expected = _encode(value, serialize_nodes=True, _geometry_cache=False)
        self.assertEqual(encode_bytes(value), expected)
        self.assertEqual(encode_bytes(value), expected)
        return expected

    def test_warm_bytes_dynamic_fields_cycles_and_equal_but_distinct_aliases(self):
        coordinate = tuple([41, 42, 43])
        terrain = ImmutableTerrainSet([coordinate, (44, 45, 46)])
        graph = dict(terrain=terrain, coordinate=coordinate, future=dict(version=1))
        graph["cycle"] = graph
        before = self.assert_complete(graph)
        # Same full map: rendering is skipped, but dynamic values stay fresh.
        graph["future"]["version"] = 2
        expected = _encode(graph, serialize_nodes=True, _geometry_cache=False)
        with patch.object(
            _NodeTemplate,
            "format",
            side_effect=AssertionError("Warm exact render must be reused"),
        ):
            self.assertEqual(encode_bytes(graph), expected)
        self.assertNotEqual(before, expected)
        graph["coordinate"] = tuple([41, 42, 43])
        self.assertNotEqual(self.assert_complete(graph), expected)
        self.assert_complete(
            dict(coordinate=coordinate, terrain=terrain, future=[graph])
        )

    def test_full_map_and_emitted_ownership_are_checked_even_when_hashes_collide(self):
        coordinate = tuple([51, 52, 53])
        terrain = ImmutableTerrainSet([coordinate, (54, 55, 56)])
        fragment = self.fragment(terrain)
        root_only = {id(terrain): 0}
        first_child = fragment.objects[1]
        child_owned_elsewhere = {id(terrain): 0, id(first_child): 1}
        with patch.object(cache, "hash", return_value=0, create=True):
            first = cache.rebase_fragment(fragment, root_only, 1)
            second = cache.rebase_fragment(fragment, child_owned_elsewhere, 2)
            third = cache.rebase_fragment(fragment, {id(terrain): 5}, 6)
        self.assertEqual(first, fragment.rebase(root_only, 1))
        self.assertEqual(second, fragment.rebase(child_owned_elsewhere, 2))
        self.assertEqual(third, fragment.rebase({id(terrain): 5}, 6))
        self.assertNotEqual(first[3], second[3])
        self.assertNotEqual(first[3], third[3])

    def test_limits_and_deadlines_do_not_remove_complete_rows(self):
        terrain = ImmutableTerrainSet([(61, 62, 63), (64, 65, 66)])
        fragment = self.fragment(terrain)
        identities = {id(terrain): 0}
        expected = fragment.rebase(identities, 1)
        with patch.object(cache, "_MAX_BYTES", 1):
            self.assertEqual(cache.rebase_fragment(fragment, identities, 1), expected)
            self.assertFalse(cache._CACHE)
        cache.rebase_fragment(fragment, identities, 1)
        now = [0.0]
        with bounded(1.0, clock=lambda: now[0]):
            now[0] = 2.0
            with self.assertRaises(TimeoutError):
                cache.rebase_fragment(fragment, identities, 1)
        cache.clear()
        with patch.object(cache, "_MAX_ENTRIES", 1):
            cache.rebase_fragment(fragment, identities, 1)
            cache.rebase_fragment(fragment, {id(terrain): 1}, 2)
            self.assertEqual(len(cache._CACHE), 1)
