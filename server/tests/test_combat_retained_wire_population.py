"""Immutable payload reuse must preserve fresh native view authority checks."""
import gc
from pathlib import Path
import sys
import unittest
import weakref
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from rift_retained_wire_benchmark import fixture
from wakfu_server import combat_effect_removal as codec
from wakfu_server import combat_retained_effects as retained
from wakfu_server import combat_retained_runtime as runtime


class RetainedWirePopulationTests(unittest.TestCase):
    def owner(self, count=1):
        owner = runtime.NativeRetainedRuntime.__new__(runtime.NativeRetainedRuntime)
        owner.fight, entries = fixture(count)
        return owner, entries

    def setUp(self):
        codec._cached_hex_identity_fields.cache_clear()
        codec._cached_identity_fields.cache_clear()

    def test_4283_payloads_reuse_after_global_lru_eviction_and_release_with_owner(self):
        owner, _ = self.owner(4283)
        first = owner.view()
        self.assertEqual(len(first.entries), 4283)
        self.assertEqual(codec._cached_identity_fields.cache_info().misses, 4283)
        codec._cached_hex_identity_fields.cache_clear()
        codec._cached_identity_fields.cache_clear()
        again = owner.view()
        self.assertEqual(again.entries, first.entries)
        self.assertEqual(codec._cached_identity_fields.cache_info().misses, 0)
        self.assertEqual(len(runtime._RETAINED_WIRE_POPULATIONS[owner]), 4283)
        removed = owner.fight.native_owned_group_effects.pop(1)["payload"]
        owner.view()
        self.assertNotIn(removed, runtime._RETAINED_WIRE_POPULATIONS[owner])
        population = runtime._RETAINED_WIRE_POPULATIONS
        own_map = population[owner]
        reference = weakref.ref(owner)
        del owner
        gc.collect()
        self.assertIsNone(reference())
        self.assertFalse(any(value is own_map for value in population.values()))

    def test_warmed_full_view_revalidates_ownership_and_does_not_install_failed_view(
        self,
    ):
        owner, _ = self.owner()
        owner.view()
        saved = runtime._RETAINED_WIRE_POPULATIONS[owner]
        row = owner.fight.native_owned_group_effects[1]
        original = row["payload"]
        row["target_id"] = 7
        with self.assertRaisesRegex(ValueError, "disagrees with owned identity"):
            owner.view()
        self.assertIs(runtime._RETAINED_WIRE_POPULATIONS[owner], saved)
        row["target_id"] = None
        owner.fight.native_retained_records[1]["manager_id"] = 999
        with self.assertRaises(ValueError):
            owner.view()
        owner.fight.native_retained_records[1]["manager_id"] = 7
        row["payload"] = "00"
        with self.assertRaises(ValueError):
            owner.view()
        self.assertIs(runtime._RETAINED_WIRE_POPULATIONS[owner], saved)
        self.assertNotIn("00", saved)
        from wakfu_server.combat_effects import _integer

        row["payload"] = codec._proto_replace(
            bytes.fromhex(original), 3, 0, _integer(3, 350553)
        ).hex()
        with self.assertRaisesRegex(ValueError, "disagrees with owned identity"):
            owner.view()
        self.assertIs(runtime._RETAINED_WIRE_POPULATIONS[owner], saved)
        row["payload"] = original
        self.assertEqual(len(owner.view().entries), 1)

    def test_nonexact_and_oversized_payloads_keep_original_fallback(self):
        class Payload(str):
            pass

        wire = retained._RetainedWirePass({})
        wire.consume()
        value = object()
        with patch.object(
            retained, "_readonly_hex_identity_fields", return_value=value
        ) as decode:
            for payload in (Payload("0801"), "00" * 4097):
                self.assertIs(wire.read(payload), value)
                self.assertIs(wire.read(payload), value)
            self.assertEqual(decode.call_count, 4)
        self.assertEqual(wire.current, {})
        with self.assertRaisesRegex(ValueError, "already consumed"):
            wire.consume()


if __name__ == "__main__":
    unittest.main()
