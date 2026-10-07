"""Exact-byte fragment tests for immutable terrain serialization."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
import unittest

_HERE = Path(__file__).resolve().parents[1]
_ROOT = _HERE.parents[1]
for _path in (str(_HERE), str(_ROOT / "server")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from wakfu_ai.context.native_context import _encode, _instance_fields
from wakfu_ai.context import native_geometry_fragments as fragments
from wakfu_ai.context.native_geometry_fragments import (
    _int_tuple_literal,
    cached_int_tuple_values,
    cache_fragment_from_encoded,
    cached_int_tuple_node,
    get_fragment,
)
from wakfu_ai.native.native_deadline import bounded
from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet


def full_encode(value):
    return _encode(value, serialize_nodes=True, _geometry_cache=False)


def local_encoded_graph(terrain):
    members = tuple(sorted(terrain))
    built = fragments._build_objects(terrain, members)
    objects, local_identities = built
    payload = json.loads(full_encode(terrain))
    nodes = [json.dumps(node, separators=(",", ":")) for node in payload["nodes"]]
    return objects, local_identities, local_identities.copy(), nodes


def serialize_rebased(fragment, identities=None, next_index=0):
    identities = {} if identities is None else dict(identities)
    root, following, assignments, rows = fragment.rebase(identities, next_index)
    identities.update(assignments)
    nodes = [None] * following
    for index, value in rows:
        nodes[index] = value
    # Test fixtures choose dense prefix refs; production fills these prefix
    # nodes before splicing the fragment.
    if any(value is None for value in nodes):
        return root, following, assignments, rows, None
    body = (
        '{"encoding":"wakfu-native-graph-1","root":{"ref":'
        + str(root)
        + '},"nodes":['
        + ",".join(nodes)
        + "]}"
    ).encode()
    return root, following, assignments, rows, body


class NativeGeometryFragmentTests(unittest.TestCase):
    def test_walkable_and_directed_edges_rebase_to_exact_complete_graph_bytes(self):
        cells = ImmutableTerrainSet((x, (x * 7) % 113, x % 3) for x in range(512))
        cell_rows = sorted(cells)
        edges = ImmutableTerrainSet(
            (cell_rows[i], cell_rows[(i + 1) % len(cell_rows)])
            for i in range(len(cell_rows))
        )
        for terrain in (cells, edges):
            calls = []

            def uncached(value):
                calls.append(value)
                return full_encode(value)

            fragment = get_fragment(terrain, uncached, _instance_fields)
            self.assertIsNotNone(fragment)
            self.assertEqual(fragment.root_index, 0)
            self.assertEqual(
                len(fragment.objects), len(json.loads(full_encode(terrain))["nodes"])
            )
            self.assertEqual(fragment.encoded_size, len(full_encode(terrain)))
            self.assertEqual(calls, [terrain])
            _, _, _, _, rebuilt = serialize_rebased(fragment)
            original = full_encode(terrain)
            self.assertEqual(rebuilt, original)
            self.assertEqual(
                hashlib.sha256(rebuilt).digest(), hashlib.sha256(original).digest()
            )

    def test_large_synthetic_geometry_is_byte_and_hash_identical(self):
        cells = ImmutableTerrainSet(
            (index, (index * 17) % 997, index % 4) for index in range(7075)
        )
        rows = sorted(cells)
        edges = ImmutableTerrainSet(
            (rows[offset], rows[(offset + stride) % len(rows)])
            for stride in (1, 2, 3, 4)
            for offset in range(7075 if stride < 4 else 3331)
        )
        self.assertEqual(len(cells), 7075)
        self.assertEqual(len(edges), 24556)
        fragment = get_fragment(edges, full_encode, _instance_fields)
        self.assertIsNotNone(fragment)
        _, _, _, _, rebuilt = serialize_rebased(fragment)
        original = full_encode(edges)
        self.assertEqual(len(rebuilt), len(original))
        self.assertEqual(
            hashlib.sha256(rebuilt).hexdigest(), hashlib.sha256(original).hexdigest()
        )
        self.assertEqual(rebuilt, original)

    def test_cache_hit_rechecks_descriptor_iterator_and_empty_fields(self):
        terrain = ImmutableTerrainSet({(0, 1, 2), (3, 4, 5)})
        calls = []
        field_checks = []

        def encoder(value):
            calls.append(value)
            return full_encode(value)

        def fields(value):
            field_checks.append(value)
            return _instance_fields(value)

        first = get_fragment(terrain, encoder, fields)
        second = get_fragment(terrain, encoder, fields)
        self.assertIs(first, second)
        self.assertEqual(calls, [terrain])
        # Initial eligibility, post-key-lock eligibility, then the cache-hit
        # eligibility check on the second invocation.
        self.assertEqual(field_checks, [terrain, terrain, terrain])
        self.assertEqual(
            first.descriptor, (type(terrain).__module__, type(terrain).__qualname__)
        )

    def test_build_false_is_hit_only_and_cold_publication_uses_existing_nodes(self):
        terrain = ImmutableTerrainSet({(0, 1, 2), (3, 4, 5)})
        self.assertIsNone(
            get_fragment(terrain, full_encode, _instance_fields, build=False)
        )
        objects, local_ids, global_ids, nodes = local_encoded_graph(terrain)
        fragment = cache_fragment_from_encoded(
            terrain, global_ids, nodes, _instance_fields
        )
        self.assertIsNotNone(fragment)
        self.assertIsNone(fragment._encoded_size)
        self.assertEqual(fragment.encoded_size, len(full_encode(terrain)))
        self.assertTrue(
            all(fragment.objects[index] is value for index, value in enumerate(objects))
        )
        self.assertEqual(fragment.rebase({}, 0)[3][0][1], nodes[0])
        self.assertIs(
            get_fragment(terrain, full_encode, _instance_fields, build=False), fragment
        )
        self.assertEqual(
            local_ids, {id(value): index for index, value in enumerate(objects)}
        )

    def test_publication_rebases_external_aliases_from_already_encoded_nodes(self):
        start, end = tuple([0, 0, 0]), tuple([1, 0, 0])
        edge = (start, end)
        terrain = ImmutableTerrainSet({edge})
        prefix = [start, end]
        context = {"prefix": prefix, "terrain": terrain}
        encoded = json.loads(full_encode(context))
        encoded_nodes = [
            json.dumps(node, separators=(",", ":")) for node in encoded["nodes"]
        ]
        # NativeGraph DFS order for this fixed fixture: context, prefix list,
        # endpoints, terrain root, then the new directed edge tuple.
        identities = {
            id(context): 0,
            id(prefix): 1,
            id(start): 2,
            id(end): 3,
            id(terrain): 4,
            id(edge): 5,
        }
        fragment = cache_fragment_from_encoded(
            terrain, identities, encoded_nodes, _instance_fields
        )
        self.assertIsNotNone(fragment)
        self.assertEqual(fragment.encoded_size, len(full_encode(terrain)))
        root, following, assignments, rows = fragment.rebase(
            {id(start): 2, id(end): 3, id(terrain): 4}, 6
        )
        self.assertEqual(root, 4)
        self.assertEqual(following, 7)
        self.assertEqual(assignments, ((id(edge), 6),))
        self.assertEqual(json.loads(rows[1][1])["items"], [{"ref": 2}, {"ref": 3}])

    def test_publication_rejects_unknown_or_malformed_existing_node_bytes(self):
        for mutate in (
            lambda value: value + ',"future":1}',
            lambda value: value[:-1] + ',"future":1}',
        ):
            terrain = ImmutableTerrainSet({(1, 2, 3)})
            _, _, identities, nodes = local_encoded_graph(terrain)
            changed = list(nodes)
            changed[0] = mutate(changed[0])
            self.assertIsNone(
                cache_fragment_from_encoded(
                    terrain, identities, changed, _instance_fields
                )
            )

        terrain = ImmutableTerrainSet({(1, 2, 3)})
        _, _, identities, nodes = local_encoded_graph(terrain)
        changed = list(nodes)
        changed[1] = b"not a string"
        self.assertIsNone(
            cache_fragment_from_encoded(terrain, identities, changed, _instance_fields)
        )

    def test_cold_coordinate_templates_reject_extra_or_reordered_leaf_fields(self):
        for mutate in (
            lambda node: node[:-1] + ',"future":1}',
            lambda node: json.dumps(
                dict(reversed(list(json.loads(node).items()))), separators=(",", ":")
            ),
        ):
            terrain = ImmutableTerrainSet({(1, 2, 3)})
            _, _, identities, nodes = local_encoded_graph(terrain)
            nodes[1] = mutate(nodes[1])
            self.assertIsNone(
                cache_fragment_from_encoded(
                    terrain, identities, nodes, _instance_fields
                )
            )

    def test_cold_directed_edge_templates_only_send_integer_leaves_to_literal_cache(
        self,
    ):
        from unittest.mock import patch

        terrain = ImmutableTerrainSet({((1, 2, 3), (4, 5, 6))})
        _, _, identities, nodes = local_encoded_graph(terrain)
        original = fragments._int_tuple_literal

        def literal(values):
            self.assertTrue(all(type(value) is int for value in values))
            return original(values)

        with patch.object(
            fragments, "_int_tuple_literal", side_effect=literal
        ) as cache:
            fragment = cache_fragment_from_encoded(
                terrain, identities, nodes, _instance_fields
            )
        self.assertIsNotNone(fragment)
        self.assertEqual(cache.call_count, 2)
        self.assertEqual(serialize_rebased(fragment)[4], full_encode(terrain))

    def test_integer_tuple_literal_cache_reuses_only_exact_known_schema(self):
        first = tuple([12, -4, 91])
        equal_but_distinct = tuple([12, -4, 91])
        self.assertIsNot(first, equal_but_distinct)
        expected = '{"type":"tuple","items":[{"value":12},{"value":-4},{"value":91}]}'
        node = {"type": "tuple", "items": [{"value": 12}, {"value": -4}, {"value": 91}]}
        first_bytes = cached_int_tuple_node(first, node)
        self.assertEqual(first_bytes, expected)
        self.assertIs(cached_int_tuple_node(equal_but_distinct, node), first_bytes)

        class TupleSubclass(tuple):
            pass

        invalid = (
            (TupleSubclass((12, -4, 91)), node),
            ((12, True, 91), node),
            (first, {"items": node["items"], "type": "tuple"}),
            (first, {"type": "tuple", "items": node["items"], "extra": 1}),
            (
                first,
                {
                    "type": "tuple",
                    "items": [{"value": 12}, {"value": True}, {"value": 91}],
                },
            ),
            (
                first,
                {
                    "type": "tuple",
                    "items": [{"value": 12, "extra": 1}, {"value": -4}, {"value": 91}],
                },
            ),
            (
                first,
                {
                    "type": "tuple",
                    "items": [{"value": 12}, {"value": -3}, {"value": 91}],
                },
            ),
        )
        for values, raw in invalid:
            with self.subTest(values=values, raw=raw):
                self.assertIsNone(cached_int_tuple_node(values, raw))

    def test_integer_tuple_cached_bytes_do_not_merge_graph_identities(self):
        left, right = tuple([8, 9, 10]), tuple([8, 9, 10])
        self.assertIsNot(left, right)
        self.assertIs(_int_tuple_literal(left), _int_tuple_literal(right))
        terrain = ImmutableTerrainSet({(left, right)})
        fragment = get_fragment(terrain, full_encode, _instance_fields)
        self.assertIsNotNone(fragment)
        self.assertEqual(len(fragment.objects), 4)
        self.assertIn(left, fragment.objects)
        self.assertIn(right, fragment.objects)
        self.assertNotEqual(id(left), id(right))
        self.assertEqual(
            len({index for _, index in fragment.rebase({}, 0)[2]}),
            len(fragment.objects),
        )

    def test_integer_tuple_cache_hit_still_checks_native_deadline(self):
        values = (4, 5, 6)
        node = {"type": "tuple", "items": [{"value": 4}, {"value": 5}, {"value": 6}]}
        self.assertIsNotNone(cached_int_tuple_node(values, node))
        with self.assertRaises(TimeoutError):
            with bounded(time.monotonic() - 1):
                cached_int_tuple_node(values, node)

    def test_exact_integer_tuple_fast_path_checks_deadline_while_scanning(self):
        values = tuple(range(4096))
        calls = 0

        def expire_during_scan():
            nonlocal calls
            calls += 1
            if calls >= 4:
                raise TimeoutError("expired during tuple scan")

        original = fragments.check
        fragments.check = expire_during_scan
        try:
            with self.assertRaises(TimeoutError):
                cached_int_tuple_values(values)
        finally:
            fragments.check = original
        self.assertGreaterEqual(calls, 4)

    def test_exact_integer_tuple_fast_path_rejects_non_exact_values_before_hash(self):
        class TupleSubclass(tuple):
            pass

        class UnhashableProbe:
            def __hash__(self):
                raise AssertionError("must not hash an ineligible tuple")

        for values in ((1, True, 3), TupleSubclass((1, 2)), (1, UnhashableProbe())):
            with self.subTest(values=values):
                self.assertIsNone(cached_int_tuple_values(values))

    def test_fallback_for_subclass_custom_tuple_and_future_instance_fields(self):
        class TerrainSubclass(ImmutableTerrainSet):
            pass

        class Coordinate(tuple):
            pass

        callback = lambda value: full_encode(value)
        self.assertIsNone(
            get_fragment(TerrainSubclass({(1, 2, 3)}), callback, _instance_fields)
        )
        self.assertIsNone(
            get_fragment(
                ImmutableTerrainSet({Coordinate((1, 2, 3))}), callback, _instance_fields
            )
        )
        terrain = ImmutableTerrainSet({(1, 2, 3)})
        self.assertIsNone(get_fragment(terrain, callback, lambda value: {"future": 1}))
        self.assertIsNone(
            get_fragment(frozenset({(1, 2, 3)}), callback, _instance_fields)
        )

    def test_exact_terrain_with_non_tuple_roots_falls_back(self):
        # Bypass the validating __new__ to model future or corrupted runtime
        # state without asking the fragment encoder to interpret it.
        terrain = frozenset.__new__(ImmutableTerrainSet, (1, 2))
        self.assertIsNone(get_fragment(terrain, full_encode, _instance_fields))

    def test_rebase_preserves_external_coordinate_aliases_and_reserved_root(self):
        start = tuple([0, 0, 0])
        end = tuple([1, 0, 0])
        terrain = ImmutableTerrainSet({(start, end)})
        fragment = get_fragment(terrain, full_encode, _instance_fields)
        self.assertIsNotNone(fragment)
        # Simulate a graph prefix that has already encoded root slot 5 and
        # these shared coordinates at indices 2 and 3.
        identities = {id(terrain): 5, id(start): 2, id(end): 3}
        root, following, assignments, rows = fragment.rebase(identities, 6)
        mapping = dict(identities)
        mapping.update(assignments)
        self.assertEqual(root, 5)
        self.assertEqual(following, 7)
        edge = next(iter(terrain))
        self.assertEqual(assignments, ((id(edge), 6),))
        # The root's edge tuple is new; the endpoint coordinate nodes remain
        # references to the graph-prefix indices, with no duplicate nodes.
        self.assertEqual(
            rows,
            (
                (5, fragment.templates[0].format([5, 6, 2, 3])),
                (6, fragment.templates[1].format([5, 6, 2, 3])),
            ),
        )
        self.assertEqual(json.loads(rows[1][1])["items"], [{"ref": 2}, {"ref": 3}])

    def test_equal_but_distinct_tuple_objects_are_not_merged(self):
        left = tuple([8, 9, 10])
        right = tuple([8, 9, 10])
        self.assertIsNot(left, right)
        terrain = ImmutableTerrainSet({(left, right)})
        fragment = get_fragment(terrain, full_encode, _instance_fields)
        self.assertIsNotNone(fragment)
        self.assertEqual(len(fragment.objects), 4)
        root, following, assignments, rows = fragment.rebase({}, 0)
        self.assertEqual(root, 0)
        self.assertEqual(following, 4)
        self.assertEqual(len(assignments), 4)
        self.assertEqual(len({index for _, index in assignments}), 4)
        self.assertEqual(len(rows), 4)

    def test_future_graph_schema_falls_back_without_rejecting_complete_encoder(self):
        terrain = ImmutableTerrainSet({(1, 2, 3)})
        original = json.loads(full_encode(terrain))
        original["nodes"][0]["futureField"] = {"value": 9}
        encoded = json.dumps(original, separators=(",", ":")).encode()
        self.assertIsNone(get_fragment(terrain, lambda _: encoded, _instance_fields))
        # The caller can still use the full encoder's bytes verbatim.
        self.assertIn(b'"futureField"', encoded)

    def test_malformed_graph_falls_back_without_publishing_cache_entry(self):
        terrain = ImmutableTerrainSet({(1, 2, 3)})
        key = (id(terrain), (type(terrain).__module__, type(terrain).__qualname__))
        self.assertIsNone(
            get_fragment(terrain, lambda _: b"{not json", _instance_fields)
        )
        self.assertNotIn(key, fragments._CACHE)

    def test_native_deadline_is_checked_and_waits_are_bounded(self):
        terrain = ImmutableTerrainSet({(1, 2, 3)})
        with self.assertRaises(TimeoutError):
            with bounded(time.monotonic() - 1):
                get_fragment(terrain, full_encode, _instance_fields)

        acquired = threading.Event()
        release = threading.Event()

        def holder():
            fragments._CACHE_LOCK.acquire()
            acquired.set()
            release.wait(1)
            fragments._CACHE_LOCK.release()

        worker = threading.Thread(target=holder)
        worker.start()
        self.assertTrue(acquired.wait(1))
        started = time.monotonic()
        try:
            with self.assertRaises(TimeoutError):
                with bounded(started + 0.02):
                    get_fragment(terrain, full_encode, _instance_fields)
        finally:
            release.set()
            worker.join(1)
        self.assertLess(time.monotonic() - started, 0.5)

    def test_failed_build_releases_per_key_lock_for_retry(self):
        terrain = ImmutableTerrainSet({(1, 2, 3)})
        key = (id(terrain), (type(terrain).__module__, type(terrain).__qualname__))
        with self.assertRaises(RuntimeError):
            get_fragment(
                terrain,
                lambda _: (_ for _ in ()).throw(RuntimeError("encoder failed")),
                _instance_fields,
            )
        self.assertNotIn(key, fragments._BUILD_LOCKS)
        self.assertIsNotNone(get_fragment(terrain, full_encode, _instance_fields))

    def test_expired_deadline_during_encoder_still_cleans_build_registry(self):
        terrain = ImmutableTerrainSet({(1, 2, 3)})
        key = (id(terrain), (type(terrain).__module__, type(terrain).__qualname__))
        deadline = time.monotonic() + 0.02

        def slow_encoder(value):
            time.sleep(0.03)
            return full_encode(value)

        with self.assertRaises(TimeoutError):
            with bounded(deadline):
                get_fragment(terrain, slow_encoder, _instance_fields)
        self.assertNotIn(key, fragments._BUILD_LOCKS)

    def test_concurrent_first_lookup_serializes_fragment_once(self):
        terrain = ImmutableTerrainSet((index, 1, 0) for index in range(200))
        entered = threading.Event()
        release = threading.Event()
        all_checked = threading.Event()
        calls = []
        checks = []
        checks_lock = threading.Lock()

        def fields(value):
            with checks_lock:
                checks.append(value)
                if len(checks) == 4:
                    all_checked.set()
            return _instance_fields(value)

        def encoder(value):
            calls.append(value)
            entered.set()
            if not release.wait(2):
                raise TimeoutError("fragment test gate timed out")
            return full_encode(value)

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(get_fragment, terrain, encoder, fields) for _ in range(4)
            ]
            self.assertTrue(entered.wait(2))
            self.assertTrue(all_checked.wait(2))
            release.set()
            results = [future.result(timeout=3) for future in futures]
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(fragment is results[0] for fragment in results))
