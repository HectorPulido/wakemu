"""Lossless partition/restore tests for the experimental native graph format."""
import copy
import hashlib
import json
import unittest

from native_context import NativeGraph, encode, encode_bytes
from native_graph_parts import FORMAT, partition, restore
from native_graph_parts import fragment_descriptor, _unpack, encode_parts, read_parts
from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet


def _json_bytes(graph):
    return json.dumps(graph, separators=(",", ":"), allow_nan=False).encode()


class NativeGraphPartsTests(unittest.TestCase):
    def test_virtual_reader_does_not_materialize_owned_terrain_or_share_mutable_rows(
        self,
    ):
        from unittest.mock import patch
        import native_graph_parts

        value = {"terrain": ImmutableTerrainSet([(41, 42, 43), (44, 45, 46)])}
        manifest, blobs = encode_parts(value)
        with patch.object(
            native_graph_parts,
            "_remap",
            side_effect=AssertionError("must stay virtual"),
        ):
            graph = read_parts(manifest, blobs.__getitem__)
        terrain_ref = graph.field(graph.data["root"], "terrain")
        exposed = graph.resolve(terrain_ref)
        exposed["items"].clear()
        graph.root["entries"].clear()
        # A mutation to a resolved row must not poison a later read from the
        # same NativeGraph or its verified process-wide blob cache.
        self.assertTrue(graph.resolve(terrain_ref)["items"])
        self.assertEqual(
            list(read_parts(manifest, blobs.__getitem__).nodes), encode(value)["nodes"]
        )

    def test_virtual_reader_rejects_corruption_missing_owners_and_bad_dynamic_references(
        self,
    ):
        manifest, blobs = encode_parts({"terrain": ImmutableTerrainSet([(51, 52, 53)])})
        for reader in ({}.__getitem__, lambda digest: b"corrupt"):
            with self.assertRaises(ValueError):
                read_parts(manifest, reader)
        invalids = []
        missing = copy.deepcopy(manifest)
        missing["nodeCount"] += 1
        invalids.append(missing)
        duplicate = copy.deepcopy(manifest)
        duplicate["dynamic"].append(duplicate["dynamic"][0])
        invalids.append(duplicate)
        root = copy.deepcopy(manifest)
        root["root"] = {"ref": root["nodeCount"]}
        invalids.append(root)
        dynamic = copy.deepcopy(manifest)
        dynamic["dynamic"][0][1]["entries"][0][1] = {"ref": dynamic["nodeCount"]}
        invalids.append(dynamic)
        for invalid in invalids:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                read_parts(invalid, blobs.__getitem__)

    def test_virtual_reader_rejects_invalid_identity_runs(self):
        manifest, blobs = encode_parts({"terrain": ImmutableTerrainSet([(61, 62, 63)])})
        fragment_count = len(json.loads(next(iter(blobs.values())))["nodes"])
        node_count = manifest["nodeCount"]
        invalids = []

        boolean = copy.deepcopy(manifest)
        boolean["fragments"][0]["indices"] = {
            "count": fragment_count,
            "runs": [[True, 1], [1, fragment_count - 1]],
        }
        invalids.append(("boolean index", boolean))

        duplicate = copy.deepcopy(manifest)
        first = duplicate["fragments"][0]["indices"]["runs"][0][0]
        duplicate["fragments"][0]["indices"] = {
            "count": fragment_count,
            "runs": [[first, 1], [first, fragment_count - 1]],
        }
        invalids.append(("duplicate indices", duplicate))

        out_of_range = copy.deepcopy(manifest)
        out_of_range["fragments"][0]["indices"] = {
            "count": fragment_count,
            "runs": [[node_count - 1, fragment_count]],
        }
        invalids.append(("out of range indices", out_of_range))

        for name, invalid in invalids:
            with self.subTest(case=name), self.assertRaises(ValueError):
                read_parts(invalid, blobs.__getitem__)

    def test_virtual_reader_rechecks_blob_checksum_after_verified_cache_warm(self):
        manifest, blobs = encode_parts({"terrain": ImmutableTerrainSet([(71, 72, 73)])})
        digest = manifest["fragments"][0]["sha256"]
        reads = []

        def reader(requested):
            reads.append(requested)
            return blobs[requested]

        first = read_parts(manifest, reader)
        terrain_ref = first.field(first.data["root"], "terrain")
        self.assertEqual(first.resolve(terrain_ref)["type"], "frozenset")
        blobs[digest] = b"corrupt bytes after first verified read"
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            read_parts(manifest, reader)
        self.assertEqual(reads, [digest, digest])

    def test_virtual_reader_rejects_duplicate_key_and_noncanonical_blob_json(self):
        manifest, blobs = encode_parts({"terrain": ImmutableTerrainSet([(81, 82, 83)])})
        original_digest = manifest["fragments"][0]["sha256"]
        original = blobs[original_digest]
        duplicate_key = original.replace(
            b'"type":"frozenset"', b'"type":"frozenset","type":"frozenset"', 1
        )
        noncanonical = b" " + original

        for label, body in (
            ("duplicate key", duplicate_key),
            ("whitespace", noncanonical),
        ):
            with self.subTest(case=label):
                invalid = copy.deepcopy(manifest)
                digest = hashlib.sha256(body).hexdigest()
                invalid["fragments"][0]["sha256"] = digest
                with self.assertRaisesRegex(ValueError, "Noncanonical"):
                    read_parts(
                        invalid, lambda requested: body if requested == digest else b""
                    )

    def test_virtual_reader_preserves_unknown_fields_on_dynamic_nodes(self):
        class FutureRuntime:
            pass

        runtime = FutureRuntime()
        runtime.future_authority = {"version": 12, "opaque": b"complete"}
        value = {"runtime": runtime, "terrain": ImmutableTerrainSet([(91, 92, 93)])}
        manifest, blobs = encode_parts(value)
        graph = read_parts(manifest, blobs.__getitem__)
        baseline = encode(value)
        self.assertEqual(list(graph.nodes), baseline["nodes"])
        runtime_node = graph.resolve(graph.field(graph.data["root"], "runtime"))
        self.assertIn("future_authority", runtime_node["fields"])
        authority = graph.resolve(runtime_node["fields"]["future_authority"])
        self.assertEqual(authority["type"], "dict")

    def test_direct_encoder_reuses_complete_blob_with_fresh_snapshot_identity_maps(
        self,
    ):
        from unittest.mock import patch
        from native_geometry_fragments import _NodeTemplate

        coordinate = tuple([31, 32, 33])
        terrain = ImmutableTerrainSet([coordinate, (34, 35, 36)])
        first, first_blobs = encode_parts(
            {"terrain": terrain, "coordinate": coordinate}
        )
        value = {"coordinate": coordinate, "future": [b"all-data"], "terrain": terrain}
        baseline = encode_bytes(value)
        with patch.object(
            _NodeTemplate,
            "format",
            side_effect=AssertionError("must reuse complete blob"),
        ):
            second, second_blobs = encode_parts(value)
        self.assertEqual(first_blobs, second_blobs)
        self.assertNotEqual(
            first["fragments"][0]["indices"], second["fragments"][0]["indices"]
        )
        self.assertEqual(
            _json_bytes(restore(second, second_blobs.__getitem__)), baseline
        )

    def test_direct_fragment_map_rejects_unallocated_external_identity(self):
        from native_geometry_fragments import get_fragment
        from native_context import _encode, _instance_fields

        coordinate = tuple([21, 22, 23])
        terrain = ImmutableTerrainSet([coordinate])
        fragment = get_fragment(
            terrain,
            lambda item: _encode(item, serialize_nodes=True, _geometry_cache=False),
            _instance_fields,
        )
        for invalid in (3, 999, True, -1):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                fragment_descriptor(
                    fragment, {id(terrain): 0, id(coordinate): invalid}, 3, "a" * 64
                )

    def test_cached_descriptor_preserves_reserved_root_and_external_alias_without_rendering(
        self,
    ):
        from unittest.mock import patch
        from native_geometry_fragments import get_fragment, _NodeTemplate
        from native_context import _encode, _instance_fields

        coordinate = tuple([7, 8, 9])
        terrain = ImmutableTerrainSet([coordinate, (10, 11, 12)])
        fragment = get_fragment(
            terrain,
            lambda item: _encode(item, serialize_nodes=True, _geometry_cache=False),
            _instance_fields,
        )
        identities = {id(terrain): 2, id(coordinate): 1}
        before = identities.copy()
        root, following, assignments, rows = fragment.rebase(identities, 3)
        with patch.object(
            _NodeTemplate, "format", side_effect=AssertionError("must not render")
        ):
            descriptor, next_index, mapped = fragment_descriptor(
                fragment, identities, 3, "a" * 64
            )
        indices = _unpack(
            descriptor["indices"],
            bound=following,
            maximum_count=len(fragment.objects),
            expected_count=len(fragment.objects),
        )
        emitted = _unpack(
            descriptor["emitted"],
            bound=len(fragment.objects),
            maximum_count=len(fragment.objects),
        )
        self.assertEqual(indices[0], root)
        self.assertEqual(
            [indices[local] for local in emitted], [index for index, _ in rows]
        )
        self.assertNotIn(1, [indices[local] for local in emitted])
        self.assertEqual((next_index, mapped), (following, assignments))
        self.assertEqual(identities, before)

    def assert_round_trip(self, value):
        graph = encode(value)
        baseline = encode_bytes(value)
        self.assertEqual(_json_bytes(graph), baseline)
        manifest, blobs = partition(graph)
        restored = restore(manifest, blobs.__getitem__)
        self.assertEqual(restored, graph)
        self.assertEqual(_json_bytes(restored), baseline)
        direct_manifest, direct_blobs = encode_parts(value)
        direct_restored = restore(direct_manifest, direct_blobs.__getitem__)
        self.assertEqual(_json_bytes(direct_restored), baseline)
        virtual = read_parts(direct_manifest, direct_blobs.__getitem__)
        self.assertEqual(list(virtual.nodes), graph["nodes"])
        self.assertEqual(virtual.data["root"], graph["root"])
        return graph, manifest, blobs, NativeGraph(restored)

    def test_round_trip_preserves_aliases_equal_objects_cycles_and_future_fields(self):
        shared_coordinate = tuple([2, 3, 1])
        equal_but_distinct = tuple([2, 3, 1])
        self.assertIsNot(shared_coordinate, equal_but_distinct)
        terrain = ImmutableTerrainSet([shared_coordinate, (4, 5, 0)])

        class FutureRuntime:
            pass

        future = FutureRuntime()
        future.capability_revision = {"unknown": [b"future", terrain]}
        value = {
            "external_coordinate": shared_coordinate,
            "equal_coordinate": equal_but_distinct,
            "terrain": terrain,
            "future_runtime": future,
        }
        value["self"] = value
        value["cycle"] = [value]

        graph, manifest, blobs, restored = self.assert_round_trip(value)
        self.assertEqual(manifest["encoding"], FORMAT)
        self.assertTrue(blobs)
        root_ref = graph["root"]
        external_ref = restored.field(root_ref, "external_coordinate")
        equal_ref = restored.field(root_ref, "equal_coordinate")
        terrain_node = restored.resolve(restored.field(root_ref, "terrain"))
        self.assertIn(external_ref, terrain_node["items"])
        self.assertNotEqual(external_ref, equal_ref)
        self.assertEqual(restored.field(root_ref, "self"), root_ref)
        cycle_ref = restored.field(root_ref, "cycle")
        cycle_node = restored.resolve(cycle_ref)
        self.assertEqual(cycle_node["items"], [root_ref])
        future_node = restored.resolve(restored.field(root_ref, "future_runtime"))
        self.assertIn("capability_revision", future_node["fields"])

    def test_shared_walkable_and_edges_keep_one_reference(self):
        shared = ImmutableTerrainSet([(0, 1, 2), (3, 4, 5)])
        graph, manifest, blobs, restored = self.assert_round_trip(
            {"walkable": shared, "edges": shared}
        )
        root_ref = graph["root"]
        self.assertEqual(
            restored.field(root_ref, "walkable"), restored.field(root_ref, "edges")
        )
        self.assertEqual(len(manifest["fragments"]), 1)
        self.assertEqual(len(blobs), 1)

    def test_equal_separate_geometry_roots_reuse_blob_without_merging_ids(self):
        first = ImmutableTerrainSet([(1, 2, 0), (4, 5, 1)])
        second = ImmutableTerrainSet([(1, 2, 0), (4, 5, 1)])
        self.assertIsNot(first, second)
        self.assertEqual(first, second)
        graph, manifest, blobs, restored = self.assert_round_trip(
            {"first": first, "second": second}
        )
        self.assertEqual(len(manifest["fragments"]), 2)
        self.assertEqual(len(blobs), 1)
        refs = [restored.field(graph["root"], name) for name in ("first", "second")]
        self.assertNotEqual(refs[0], refs[1])
        self.assertEqual(
            [fragment["sha256"] for fragment in manifest["fragments"]],
            [next(iter(blobs)), next(iter(blobs))],
        )

    def test_future_or_non_native_geometry_and_custom_tuple_fields_fall_back_whole(
        self,
    ):
        class FutureTerrain(ImmutableTerrainSet):
            pass

        class Coordinate(tuple):
            pass

        future_terrain = FutureTerrain([(1, 2, 3)])
        future_terrain.extension = {"version": 9}
        custom_coordinate = Coordinate((1, 2, 3))
        custom_coordinate.extension = b"coordinate-state"
        values = (
            {"future_terrain": future_terrain},
            {"plain_frozenset": frozenset({(1, 2, 3)})},
            {
                "custom_coordinate": ImmutableTerrainSet(
                    [(custom_coordinate, (4, 5, 6))]
                )
            },
        )
        for value in values:
            with self.subTest(value=type(next(iter(value.values()))).__name__):
                graph = encode(value)
                manifest, blobs = partition(graph)
                self.assertEqual(manifest, graph)
                self.assertEqual(blobs, {})
                self.assertEqual(restore(manifest, blobs.__getitem__), graph)

    def test_missing_and_corrupt_fragment_blobs_are_rejected(self):
        graph = encode({"terrain": ImmutableTerrainSet([(1, 2, 3), (4, 5, 6)])})
        manifest, blobs = partition(graph)
        digest = manifest["fragments"][0]["sha256"]
        with self.assertRaisesRegex(ValueError, "Missing native fragment"):
            restore(manifest, {}.__getitem__)
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            restore(
                manifest,
                lambda requested: b"corrupt"
                if requested == digest
                else blobs[requested],
            )

    def test_future_fields_on_canonical_terrain_remain_complete_dynamic_data(self):
        graph = encode({"terrain": ImmutableTerrainSet([(1, 2, 3)])})
        native = NativeGraph(graph)
        terrain = native.resolve(native.field(graph["root"], "terrain"))
        terrain["fields"]["future_capability"] = {"value": 19}
        manifest, blobs = partition(graph)
        self.assertEqual(manifest, graph)
        self.assertEqual(blobs, {})
        self.assertEqual(
            _json_bytes(restore(manifest, blobs.__getitem__)), _json_bytes(graph)
        )

    def test_self_referencing_terrain_falls_back_and_forged_count_is_rejected(self):
        graph = encode({"terrain": ImmutableTerrainSet([(1, 2, 3)])})
        native = NativeGraph(graph)
        terrain_ref = native.field(graph["root"], "terrain")
        native.resolve(terrain_ref)["items"] = [terrain_ref]
        manifest, blobs = partition(graph)
        self.assertEqual(manifest, graph)
        self.assertEqual(blobs, {})
        self.assertEqual(restore(manifest, blobs.__getitem__), graph)

        manifest, blobs = partition(
            encode({"terrain": ImmutableTerrainSet([(1, 2, 3)])})
        )
        manifest["nodeCount"] = 2**62
        with self.assertRaisesRegex(
            ValueError, "Incomplete native parts node ownership"
        ):
            restore(manifest, blobs.__getitem__)

    def test_malformed_owner_maps_and_root_are_rejected(self):
        graph = encode({"terrain": ImmutableTerrainSet([(1, 2, 3)])})
        manifest, blobs = partition(graph)

        duplicate = copy.deepcopy(manifest)
        duplicate["dynamic"].append(copy.deepcopy(duplicate["dynamic"][0]))
        out_of_bounds = copy.deepcopy(manifest)
        out_of_bounds["fragments"][0]["indices"] = {
            "count": 2,
            "runs": [[out_of_bounds["nodeCount"] - 1, 2]],
        }
        missing_owner = copy.deepcopy(manifest)
        missing_owner["fragments"][0]["emitted"] = {"count": 1, "runs": [[0, 1]]}
        malformed_root = copy.deepcopy(manifest)
        malformed_root["root"] = {"ref": malformed_root["nodeCount"]}

        for invalid in (duplicate, out_of_bounds, missing_owner, malformed_root):
            with self.subTest(manifest=invalid):
                with self.assertRaises(ValueError):
                    restore(invalid, blobs.__getitem__)

    def test_packed_identity_runs_reject_malformed_ranges_before_expansion(self):
        graph = encode({"terrain": ImmutableTerrainSet([(1, 2, 3)])})
        manifest, blobs = partition(graph)
        fragment_count = len(json.loads(next(iter(blobs.values())))["nodes"])
        node_count = manifest["nodeCount"]

        malformed = []
        count_mismatch = copy.deepcopy(manifest)
        count_mismatch["fragments"][0]["indices"]["count"] = fragment_count + 1
        malformed.append(("indices count mismatch", count_mismatch))

        sum_mismatch = copy.deepcopy(manifest)
        sum_mismatch["fragments"][0]["indices"] = {
            "count": fragment_count,
            "runs": [[0, fragment_count - 1]],
        }
        malformed.append(("run sum mismatch", sum_mismatch))

        duplicate_run = copy.deepcopy(manifest)
        duplicate_run["fragments"][0]["indices"] = {
            "count": fragment_count,
            "runs": [[0, 1], [0, fragment_count - 1]],
        }
        malformed.append(("duplicate identity", duplicate_run))

        bool_run = copy.deepcopy(manifest)
        bool_run["fragments"][0]["indices"] = {
            "count": fragment_count,
            "runs": [[True, 1], [1, fragment_count - 1]],
        }
        malformed.append(("boolean run value", bool_run))

        giant_fragment_count = copy.deepcopy(manifest)
        giant_fragment_count["fragments"][0]["indices"]["count"] = 2**62
        malformed.append(("forged fragment count", giant_fragment_count))

        for name, invalid in malformed:
            with self.subTest(case=name):
                with self.assertRaises(ValueError):
                    restore(invalid, blobs.__getitem__)

        # Global identity bounds and local emitted-index bounds are different:
        # index runs address nodeCount, emitted runs address fragment nodes.
        bad_global_bound = copy.deepcopy(manifest)
        bad_global_bound["fragments"][0]["indices"] = {
            "count": fragment_count,
            "runs": [[node_count - 1, fragment_count]],
        }
        with self.assertRaises(ValueError):
            restore(bad_global_bound, blobs.__getitem__)

        bad_emitted_bound = copy.deepcopy(manifest)
        bad_emitted_bound["fragments"][0]["emitted"] = {
            "count": 2,
            "runs": [[fragment_count - 1, 2]],
        }
        with self.assertRaises(ValueError):
            restore(bad_emitted_bound, blobs.__getitem__)

    def test_alias_conflict_compares_canonical_bytes_not_python_numeric_equality(self):
        graph = encode({"terrain": ImmutableTerrainSet([(1, 2, 3)])})
        manifest, blobs = partition(graph)
        conflict = copy.deepcopy(manifest)
        fragment = conflict["fragments"][0]
        coordinates = [
            value
            for start, length in fragment["indices"]["runs"]
            for value in range(start, start + length)
        ]
        coordinate_local = next(
            i for i, identity in enumerate(coordinates) if identity != coordinates[0]
        )
        coordinate_identity = coordinates[coordinate_local]
        fragment["emitted"] = {"count": 1, "runs": [[0, 1]]}
        conflict["dynamic"].append(
            [
                coordinate_identity,
                {
                    "type": "tuple",
                    "items": [{"value": 1.0}, {"value": 2}, {"value": 3}],
                },
            ]
        )
        self.assertEqual({"value": 1}, {"value": 1.0})
        with self.assertRaisesRegex(ValueError, "Conflicting native fragment alias"):
            restore(conflict, blobs.__getitem__)

    def test_partition_and_restore_do_not_mutate_caller_owned_data(self):
        value = {
            "walkable": ImmutableTerrainSet(((x, x % 17, x % 3) for x in range(128)))
        }
        cells = sorted(value["walkable"])
        value["edges"] = ImmutableTerrainSet(
            [(cells[i], cells[(i + 1) % len(cells)]) for i in range(len(cells))]
            + [(cells[(i + 1) % len(cells)], cells[i]) for i in range(len(cells))]
        )
        graph = encode(value)
        graph_before = copy.deepcopy(graph)
        manifest, blobs = partition(graph)
        manifest_before = copy.deepcopy(manifest)
        blobs_before = dict(blobs)
        self.assertEqual(graph, graph_before)
        restored = restore(manifest, blobs.__getitem__)
        self.assertEqual(manifest, manifest_before)
        self.assertEqual(blobs, blobs_before)
        self.assertEqual(_json_bytes(restored), encode_bytes(value))
        self.assertGreater(len(manifest["fragments"]), 0)
        self.assertEqual(
            hashlib.sha256(next(iter(blobs.values()))).hexdigest(), next(iter(blobs))
        )


if __name__ == "__main__":
    unittest.main()
