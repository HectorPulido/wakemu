import copy
import unittest

from wakfu_server.combat_trove_long_map import NativeTroveLongMap


class NativeTroveLongMapTests(unittest.TestCase):
    def test_actual_native_default_constructor_and_order(self):
        mapping = NativeTroveLongMap()
        self.assertEqual(len(mapping.state["keys"]), 23)
        self.assertEqual(mapping.state["compact_removes"], 10)
        for identity in (9, 2, -4, -1, 8):
            mapping.put(identity)
        self.assertEqual(mapping.order(), (9, 8, -4, 2, -1))
        mapping.remove(2)
        mapping.put(20)
        self.assertEqual(mapping.order(), (20, 9, 8, -4, -1))

    def test_checkpoint_preserves_removed_slots_and_future_order(self):
        original = NativeTroveLongMap()
        for identity in range(-20, 20):
            original.put(identity)
        for identity in range(-15, 15, 3):
            original.remove(identity)
        restored = NativeTroveLongMap(copy.deepcopy(original.state))
        for identity in (100, -100, 20, 3, 1 << 40):
            original.put(identity)
            restored.put(identity)
        self.assertEqual(restored.state, original.state)

    def test_duplicate_put_does_not_consume_size_or_free(self):
        mapping = NativeTroveLongMap()
        mapping.put(0)
        before = copy.deepcopy(mapping.state)
        self.assertFalse(mapping.put(0))
        self.assertEqual(mapping.state, before)

    def test_absent_removal_does_not_trigger_compaction(self):
        mapping = NativeTroveLongMap()
        before = copy.deepcopy(mapping.state)
        self.assertFalse(mapping.remove(-1))
        self.assertEqual(mapping.state, before)

    def test_signed_long_hash_keeps_native_upper_bits(self):
        mapping = NativeTroveLongMap()
        for identity in (0, -1, -(1 << 63), (1 << 63) - 1, 1 << 32):
            mapping.put(identity)
        self.assertTrue(
            all(
                mapping.contains(identity)
                for identity in (0, -1, -(1 << 63), (1 << 63) - 1, 1 << 32)
            )
        )
        with self.assertRaisesRegex(ValueError, "signed-long"):
            mapping.put(1 << 63)

    def test_invalid_persisted_topology_is_rejected(self):
        state = NativeTroveLongMap().state
        state["size"] = 1
        with self.assertRaisesRegex(ValueError, "topology"):
            NativeTroveLongMap(state)
