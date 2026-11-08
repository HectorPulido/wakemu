"""Shared scalar envelopes remain immutable and never retain weak owners."""
import gc
from types import MappingProxyType
import unittest
import weakref

from wakfu_server import combat_retained_runtime as runtime


class SharedRetainedEnvelopeTests(unittest.TestCase):
    def setUp(self):
        runtime._cached_retained_record.cache_clear()
        runtime._RETAINED_POPULATIONS.clear()

    def tearDown(self):
        runtime._cached_retained_record.cache_clear()
        runtime._RETAINED_POPULATIONS.clear()

    def owner(self):
        return runtime.NativeRetainedRuntime.__new__(runtime.NativeRetainedRuntime)

    def rows(self):
        return {
            901: dict(
                uid=901,
                target_id=7,
                manager_id=7,
                effect_class=400,
                generic_effect=1,
                definition_dispellable=True,
            )
        }

    def test_two_owner_source_mutation_isolated_from_shared_readonly_envelope(self):
        first_owner, second_owner = self.owner(), self.owner()
        first_rows, second_rows = self.rows(), self.rows()
        first = runtime._retained_population(first_owner, first_rows, (901,))
        second = runtime._retained_population(second_owner, second_rows, (901,))
        envelope = runtime._RETAINED_POPULATIONS[first_owner][901]
        self.assertIs(envelope, runtime._RETAINED_POPULATIONS[second_owner][901])
        self.assertIs(first[0], second[0])
        self.assertIs(type(envelope[0]), MappingProxyType)
        self.assertEqual(envelope[0], first_rows[901])
        with self.assertRaises(TypeError):
            envelope[0]["generic_effect"] = 99
        second_rows[901]["generic_effect"] = 2
        changed = runtime._retained_population(second_owner, second_rows, (901,))
        self.assertEqual(changed[0].generic_effect, 2)
        self.assertEqual(first[0].generic_effect, 1)
        self.assertEqual(envelope[0]["generic_effect"], 1)
        self.assertEqual(first_rows[901]["generic_effect"], 1)
        self.assertIs(
            runtime._retained_population(first_owner, first_rows, (901,))[0], first[0]
        )
        self.assertIsNot(runtime._RETAINED_POPULATIONS[second_owner][901], envelope)
        self.assertIs(runtime._retained_record(self.rows()[901]), first[0])

    def test_shared_lru_envelope_does_not_retain_either_owner(self):
        first_owner, second_owner = self.owner(), self.owner()
        first_ref, second_ref = weakref.ref(first_owner), weakref.ref(second_owner)
        rows = self.rows()
        runtime._retained_population(first_owner, rows, (901,))
        runtime._retained_population(second_owner, self.rows(), (901,))
        envelope = runtime._RETAINED_POPULATIONS[first_owner][901]
        self.assertIs(envelope, runtime._RETAINED_POPULATIONS[second_owner][901])
        del first_owner, second_owner
        gc.collect()
        self.assertIsNone(first_ref())
        self.assertIsNone(second_ref())
        self.assertEqual(len(runtime._RETAINED_POPULATIONS), 0)
        self.assertEqual(runtime._cached_retained_record.cache_info().currsize, 1)
        self.assertIs(runtime._retained_record(rows[901]), envelope[2])
        self.assertIs(type(envelope[0]), MappingProxyType)
        self.assertIs(type(envelope[1]), tuple)
        self.assertTrue(all(type(part) is tuple for part in envelope[1]))
        with self.assertRaises(TypeError):
            envelope[0]["target_id"] = 8
        rows[901]["target_id"] = 8
        self.assertEqual(envelope[0]["target_id"], 7)
        self.assertEqual(envelope[2].target_id, 7)
