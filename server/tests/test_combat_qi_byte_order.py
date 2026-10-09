"""Persist actual per-cell Trove history through QK lifecycle operations."""
import unittest

from wakfu_server.combat_qi_registry import NativeQIRegistry
from wakfu_server.combat_trove_byte_set import NativeTroveByteSet


class NativeQIByteOrderTests(unittest.TestCase):
    def registry(self):
        return NativeQIRegistry(
            dict(x=0, y=0, width=2, height=1, cell_masks=[0, 0]), [None] * 127
        )

    def row(self, identity, position=(0, 0)):
        return dict(
            identity=["actor", identity],
            position=position,
            radius=0,
            indexed=False,
            movement_blocking=True,
        )

    def test_unknown_order_remains_unknown(self):
        registry = self.registry()
        registry.register(self.row(9))
        with self.assertRaisesRegex(ValueError, "iterator topology"):
            registry.ordered_U(0, 0)

    def test_fresh_untouched_cell_has_no_candidates_without_becoming_touched(self):
        registry = self.registry()
        registry.capture_fresh_cell_topology([])
        self.assertIsNone(registry.snapshot().U(1, 0))
        self.assertEqual(registry.ordered_U(1, 0), ())
        self.assertIsNone(registry.snapshot().U(1, 0))
        self.assertNotIn("1,0", registry.serialized_byte_topology())

    def test_registration_move_toggle_removal_and_checkpoint(self):
        registry = self.registry()
        registry.capture_fresh_cell_topology([])
        expected = NativeTroveByteSet()
        for identity in range(20):
            slot = registry.register(self.row(identity))
            expected.put(slot)
        self.assertEqual(registry.ordered_U(0, 0), expected.order())
        registry.move(3, ["actor", 3], (1, 0))
        expected.remove(3)
        self.assertEqual(registry.ordered_U(0, 0), expected.order())
        self.assertEqual(registry.ordered_U(1, 0), (3,))
        registry.toggle(3, ["actor", 3], False)
        self.assertEqual(registry.ordered_U(1, 0), ())
        registry.toggle(3, ["actor", 3], True)
        self.assertEqual(registry.ordered_U(1, 0), (3,))
        registry.remove(3, ["actor", 3])
        restored = NativeQIRegistry(
            dict(x=0, y=0, width=2, height=1, cell_masks=[0, 0]),
            registry.serialized_slots(),
            touched_cells=registry.serialized_cells(),
            byte_topology=registry.serialized_byte_topology(),
        )
        self.assertEqual(restored.ordered_U(0, 0), expected.order())
        self.assertEqual(restored.ordered_U(1, 0), ())
        self.assertIn("1,0", restored.serialized_byte_topology())
