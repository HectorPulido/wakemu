"""Staged static LOS proof tests; no native runtime, DB or gameplay mutation."""
from collections import Counter
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import gc
import json
import os
from pathlib import Path
import tempfile
from types import MappingProxyType
import unittest
import weakref
from unittest.mock import patch

from wakfu_server import combat_native_los_ray as ray
from wakfu_server import combat_los_runtime_seal as seal
from wakfu_server import prepared_los
from wakfu_server import combat_input_observation as observation

REVISION = "a" * 64
SOURCE = dict(
    schema="native-Sf-Vz-columns-v1",
    map_id=17,
    columns=[
        [0, 0, [[9, 2, True]]],
        [1, 0, [[10, 20, True]]],
        [0, 0, [[20, 30, True], [10, 30, False]]],
        [2, 0, [[10, 20, True]]],
    ],
)
PROGRAM = dict(
    schema="native-Sf-bfZ-int-v1", instructions=[["constant", 1], ["ireturn"]]
)


class RuntimeLosSealTests(unittest.TestCase):
    def setUp(self):
        ray.topology_columns.cache_clear()
        ray.ray_program.cache_clear()
        ray.static_ray.cache_clear()
        seal._COLUMNS.clear()
        seal._GENERATIONS.clear()
        seal._PROGRAM = None
        prepared_los._published.cache_clear()
        prepared_los._inventory.cache_clear()
        self.addCleanup(self.clear)

    def clear(self):
        ray.topology_columns.cache_clear()
        ray.ray_program.cache_clear()
        ray.static_ray.cache_clear()
        seal._COLUMNS.clear()
        seal._GENERATIONS.clear()
        seal._PROGRAM = None
        prepared_los._published.cache_clear()
        prepared_los._inventory.cache_clear()

    def inputs(self):
        source, program, calls = deepcopy(SOURCE), deepcopy(PROGRAM), Counter()

        def read(name):
            calls[name] += 1
            return json.dumps(
                program if name == "native-los-ray-program.json" else source
            ).encode()

        return source, program, calls, read

    def load(self, read):
        return (
            patch.object(
                ray.protocol_catalog, "read_published_bytes", side_effect=read
            ),
            patch.object(ray.protocol_catalog, "release", return_value=REVISION),
            patch.object(ray.protocol_catalog, "exists", return_value=True),
            patch.object(prepared_los, "published_columns", return_value=None),
        )

    def test_native_loader_seals_once_preserving_overwrite_order_and_shared_values(
        self,
    ):
        source, program, calls, read = self.inputs()
        with self.load(read)[0], self.load(read)[1], self.load(read)[2], self.load(
            read
        )[3]:
            first = ray.sealed_generation(17)
            columns = ray.topology_columns(17)
            self.assertIsNotNone(first)
            self.assertIs(first, ray.sealed_generation(17))
            self.assertEqual(list(columns), [(0, 0), (1, 0), (2, 0)])
            self.assertEqual(columns[(0, 0)], ((20, 30, True), (10, 30, False)))
            self.assertIs(columns[(1, 0)], columns[(2, 0)])
            self.assertEqual(columns, ray.prepare_columns(source, 17))
            self.assertEqual(sum(calls.values()), 2)
            for _ in range(40):
                self.assertIs(ray.sealed_generation(17), first)
            self.assertEqual(sum(calls.values()), 2)
            self.assertEqual(first.map_id, 17)
            self.assertEqual(first.release, REVISION)
            self.assertEqual(
                first.topology_sha,
                hashlib.sha256(json.dumps(source).encode()).hexdigest(),
            )
            self.assertEqual(
                first.ray_program_sha,
                hashlib.sha256(json.dumps(program).encode()).hexdigest(),
            )
            source["columns"][1][2][0][0] = 900
            self.assertEqual(columns[(1, 0)][0][0], 10)
            with self.assertRaises(TypeError):
                columns[(9, 9)] = ()
            with self.assertRaises(TypeError):
                columns[(1, 0)][0] = (0, 0, False)
            with self.assertRaises(FrozenInstanceError):
                first.map_id = 99

    def test_mutable_or_foreign_mapping_aliases_cannot_claim_generation(self):
        _, _, _, read = self.inputs()
        with self.load(read)[0], self.load(read)[1], self.load(read)[2], self.load(
            read
        )[3]:
            actual = ray.sealed_generation(17)
            columns = dict(ray.topology_columns(17))
            with patch.object(ray, "topology_columns", return_value=columns):
                self.assertIsNone(ray.sealed_generation(17))
            with patch.object(
                ray, "topology_columns", return_value=MappingProxyType(columns)
            ):
                self.assertIsNone(ray.sealed_generation(17))
            columns[(1, 0)] = ((999, 1, True),)
            self.assertEqual(ray.topology_columns(17)[(1, 0)][0][0], 10)
            self.assertIs(ray.sealed_generation(17), actual)

    def test_deep_validation_rejects_nested_mutables_and_scalar_lookalikes(self):
        bad = [
            {(0, 0): (([], 2, True),)},
            {(0, 0): ([1, 2, True],)},
            {(0, 0): ((1, 2, 1),)},
            {(False, 0): ((1, 2, True),)},
            {(0, 0): ((1, 2.0, True),)},
            {(0, 0): ((1, 2, True, 0),)},
        ]
        for columns in bad:
            with self.subTest(columns=columns):
                self.assertIsNone(
                    seal._publish_owned_columns(
                        columns, map_id=17, release=REVISION, source_sha="b" * 64
                    )
                )
        for program in (
            (("constant", []), ("ireturn",)),
            (("unknown",),),
            (("constant", True), ("ireturn",)),
            (("goto", 100),),
        ):
            self.assertFalse(
                seal._publish_owned_program(
                    program, release=REVISION, source_sha="c" * 64
                )
            )

    def test_capture_and_replay_bypass_before_any_loader_or_catalog_read(self):
        empty = dict(
            schema="wakemu-combat-observed-inputs-v1",
            events=[],
            rng_streams=[],
            incomplete=[],
        )
        with patch.object(ray, "topology_columns", side_effect=AssertionError("read")):
            with observation.observe_combat_inputs():
                self.assertIsNone(ray.sealed_generation(17))
            with observation.replay_combat_inputs(empty):
                self.assertIsNone(ray.sealed_generation(17))

    def test_changed_release_or_program_identity_invalidates_proof(self):
        _, _, _, read = self.inputs()
        with self.load(read)[0], self.load(read)[1], self.load(read)[2], self.load(
            read
        )[3]:
            self.assertIsNotNone(ray.sealed_generation(17))
            program = ray.ray_program()
            columns = ray.topology_columns(17)
            self.assertIsNone(seal._generation(18, REVISION, columns, program))
            with patch.object(ray.protocol_catalog, "release", return_value="d" * 64):
                self.assertIsNone(ray.sealed_generation(17))
            with patch.object(ray, "ray_program", return_value=tuple(list(program))):
                self.assertIsNone(ray.sealed_generation(17))
            with self.assertRaises(TypeError):
                seal._SealedGeneration(None, 17, REVISION, "b" * 64, "c" * 64)

    def test_release_change_during_verified_read_is_rejected(self):
        _, _, _, read = self.inputs()
        with patch.object(
            ray.protocol_catalog, "read_published_bytes", side_effect=read
        ), patch.object(
            ray.protocol_catalog, "release", side_effect=[REVISION, "d" * 64]
        ):
            with self.assertRaisesRegex(ValueError, "release changed"):
                ray._verified_source("native-los-ray-program.json")
        self.assertEqual(len(seal._COLUMNS), 0)

    def test_custom_mutable_loader_keeps_legacy_reader_without_admission(self):
        def load(path):
            return deepcopy(
                PROGRAM if Path(path).name == "native-los-ray-program.json" else SOURCE
            )

        with patch.object(ray.protocol_catalog, "load", side_effect=load), patch.object(
            ray.protocol_catalog, "exists", return_value=True
        ), patch.object(
            ray.protocol_catalog, "release", return_value=REVISION
        ), patch.object(
            prepared_los, "published_columns", return_value=None
        ):
            columns = ray.topology_columns(17)
            self.assertIs(type(columns), dict)
            columns[(9, 9)] = ()
            self.assertIsNone(ray.sealed_generation(17))
            self.assertEqual(
                ray.static_ray(17, (0, 0, 0), (2, 0, 0)), (True, frozenset())
            )

    def test_existing_prepared_artifact_receives_same_deep_source_bound_proof(self):
        source_raw = json.dumps(SOURCE).encode()
        digest = hashlib.sha256(source_raw).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            expected = prepared_los.build_artifact(
                directory, map_id=17, revision=REVISION, source_raw=source_raw
            )
            _, _, calls, read = self.inputs()
            with patch.dict(
                os.environ, {"WAKFU_PREPARED_LOS_DIR": directory}
            ), patch.object(
                ray.protocol_catalog, "release", return_value=REVISION
            ), patch.object(
                ray.protocol_catalog,
                "document_hashes",
                return_value={"native-los-topology/17.json": digest},
            ), patch.object(
                ray.protocol_catalog, "read_published_bytes", side_effect=read
            ):
                generation = ray.sealed_generation(17)
                self.assertIsNotNone(generation)
                self.assertEqual(generation.topology_sha, digest)
                self.assertEqual(
                    list(ray.topology_columns(17).items()), list(expected.items())
                )
                self.assertIsNot(ray.topology_columns(17), expected)
                self.assertEqual(calls, {"native-los-ray-program.json": 1})

    def test_uncertified_program_retains_original_reader_behavior(self):
        _, program, _, read = self.inputs()
        program["instructions"] = [["constant", True], ["ireturn"]]
        with self.load(read)[0], self.load(read)[1], self.load(read)[2], self.load(
            read
        )[3]:
            self.assertIsNone(ray.sealed_generation(17))
            self.assertEqual(
                ray.static_ray(17, (0, 0, 0), (2, 0, 0)), (True, frozenset())
            )

    def test_prepare_columns_remains_owned_mutable_builder_for_offline_artifacts(self):
        source = deepcopy(SOURCE)
        columns = ray.prepare_columns(source, 17)
        self.assertIs(type(columns), dict)
        columns[(9, 9)] = ()
        self.assertIs(columns[(1, 0)], columns[(2, 0)])
        self.assertIsNone(seal._generation(17, REVISION, columns, (("ireturn",),)))

    def test_tokens_do_not_keep_evicted_native_topology_maps_alive(self):
        _, _, _, read = self.inputs()
        with self.load(read)[0], self.load(read)[1], self.load(read)[2], self.load(
            read
        )[3]:
            token = ray.sealed_generation(17)
            reference = weakref.ref(ray.topology_columns(17))
            with self.assertRaises(AttributeError):
                del ray.topology_columns(17)._SealedColumns__proxy
            ray.topology_columns.cache_clear()
            gc.collect()
            self.assertIsNone(reference())
            self.assertFalse(seal._COLUMNS)
            self.assertIsNot(ray.sealed_generation(17), token)
