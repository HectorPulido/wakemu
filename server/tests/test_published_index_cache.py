"""Focused immutable publication-cache contract; no gameplay or database writes."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import gc
from threading import Barrier
import unittest
from unittest.mock import patch
import weakref

from wakfu_server import combat_published_catalogs as catalogs
from wakfu_server.combat_original_producer_events import original_output_index


class Reader:
    representation = "frozen_effect"

    def __init__(self, generation="a", rows=None):
        self.descriptor = dict(
            policy=catalogs.POLICY,
            revision=generation * 64,
            manifest_sha256=generation * 64,
            collection="player.effects",
            count=1,
            ordered_keys_sha256="c" * 64,
        )
        self.rows = [["27", 400, [166, 208]]] if rows is None else rows
        self.calls = 0

    def original_output_index(self):
        self.calls += 1
        return deepcopy(self.rows)


def resolve(reader):
    with patch(
        "wakfu_server.native_compiled_catalog.published_collection", return_value=reader
    ):
        return catalogs.resolve_static_catalog_descriptor(reader.descriptor)


class PublishedIndexCacheTests(unittest.TestCase):
    def test_immutable_reuse_deepcopy_and_owner_lifetime(self):
        reader = Reader()
        reader_ref = weakref.ref(reader)
        mapping = resolve(reader)
        first = original_output_index(mapping)
        self.assertEqual(first["27"], (400, frozenset((166, 208))))
        self.assertIs(original_output_index(deepcopy(mapping)), first)
        self.assertEqual(reader.calls, 1)
        with self.assertRaises(TypeError):
            first["27"] = (1, frozenset())
        with self.assertRaises(AttributeError):
            first["27"][1].add(999)
        with self.assertRaises(TypeError):
            mapping._original_output_index = {}
        del mapping, reader
        gc.collect()
        self.assertIsNone(reader_ref())
        self.assertIn("27", first)

    def test_exact_mapping_and_generation_isolation_and_stale_rejection(self):
        first_reader = Reader()
        second_reader = Reader("b", [["28", 400, [999]]])
        first, second = resolve(first_reader), resolve(second_reader)
        self.assertNotEqual(original_output_index(first), original_output_index(second))
        reopened = resolve(first_reader)
        self.assertIsNot(original_output_index(reopened), original_output_index(first))
        self.assertEqual(first_reader.calls, 2)
        with patch(
            "wakfu_server.native_compiled_catalog.published_collection",
            side_effect=ValueError(
                "Serialized compiled descriptor belongs to a stale publication"
            ),
        ):
            with self.assertRaisesRegex(ValueError, "stale publication"):
                catalogs.resolve_static_catalog_descriptor(first_reader.descriptor)

    def test_invalid_first_read_is_not_cached(self):
        reader = Reader(rows=[["27", 400, []]])
        mapping = resolve(reader)
        for _ in range(2):
            with self.assertRaisesRegex(
                ValueError, "Invalid published original output identity"
            ):
                original_output_index(mapping)
        self.assertEqual(reader.calls, 2)
        self.assertIsNone(mapping._original_output_index)
        reader.rows = [["27", 400, [166]]]
        self.assertEqual(original_output_index(mapping)["27"][1], frozenset((166,)))
        self.assertEqual(reader.calls, 3)

    def test_concurrent_first_read_publishes_one_complete_index(self):
        reader = Reader()
        mapping = resolve(reader)
        barrier = Barrier(8)

        def read(_):
            barrier.wait(timeout=5)
            return original_output_index(mapping)

        with ThreadPoolExecutor(max_workers=8) as workers:
            results = list(workers.map(read, range(8)))
        self.assertTrue(all(value is results[0] for value in results))
        self.assertEqual(reader.calls, 1)

    def test_non_effect_and_unsealed_input_keep_existing_behavior(self):
        reader = Reader()
        reader.representation = "native_json"
        self.assertEqual(original_output_index(resolve(reader)), {})
        self.assertEqual(reader.calls, 0)
        with self.assertRaises(TypeError):
            catalogs.published_original_output_index({})
