import unittest

from wakfu_server.combat.combat_qi_registry import NativeQIRegistry


class NativeQIRegistryTest(unittest.TestCase):
    def registry(self, slots=None):
        return NativeQIRegistry(
            dict(x=0, y=0, width=4, height=4, cell_masks=[0] * 16),
            [None] * 127 if slots is None else slots,
        )

    def row(self, uid, position=(1, 1), radius=0):
        return dict(
            identity=("effect_area", uid),
            indexed=False,
            movement_blocking=False,
            position=position,
            radius=radius,
        )

    def test_requires_complete_slots(self):
        with self.assertRaisesRegex(ValueError, "complete"):
            self.registry([])

    def test_area_and_actor_share_slots_and_removed_holes(self):
        registry = self.registry()
        self.assertEqual(registry.register(self.row(10)), 0)
        actor = self.row(10)
        actor["identity"] = ("actor", 10)
        self.assertEqual(registry.register(actor), 1)
        registry.remove(0, ("effect_area", 10))
        self.assertEqual(registry.register(self.row(11)), 0)
        self.assertEqual(registry.snapshot().U(1, 1), frozenset((0, 1)))

    def test_outside_anchor_reserves_without_spatial_membership(self):
        registry = self.registry()
        self.assertEqual(registry.register(self.row(1, (-1, 1), 2)), 0)
        self.assertIsNone(registry.snapshot().U(0, 1))
        self.assertEqual(registry.register(self.row(2)), 1)

    def test_square_radius_clips_without_circle_filter(self):
        registry = self.registry()
        registry.register(self.row(1, (0, 0), 1))
        self.assertEqual(registry.snapshot().U(1, 1), frozenset((0,)))
        self.assertIsNone(registry.snapshot().U(2, 0))

    def test_full_slots_return_minus_one_without_mutation(self):
        registry = self.registry()
        for uid in range(127):
            self.assertEqual(registry.register(self.row(uid)), uid)
        before = registry.serialized_slots()
        self.assertEqual(registry.register(self.row(128)), -1)
        self.assertEqual(registry.serialized_slots(), before)

    def test_wrong_identity_does_not_release_slot(self):
        registry = self.registry()
        registry.register(self.row(1))
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            registry.remove(0, ("actor", 1))
        self.assertEqual(registry.register(self.row(2)), 1)

    def test_toggle_retains_slot_and_move_reindexes(self):
        registry = self.registry()
        registry.register(self.row(1))
        registry.toggle(0, ("effect_area", 1), False)
        self.assertEqual(registry.snapshot().U(1, 1), frozenset())
        self.assertEqual(registry.register(self.row(2)), 1)
        registry.move(0, ("effect_area", 1), (2, 2))
        self.assertEqual(registry.snapshot().U(2, 2), frozenset((0,)))
        registry.move(0, ("effect_area", 1), (-1, 2))
        self.assertEqual(registry.snapshot().U(2, 2), frozenset())
        registry.toggle(0, ("effect_area", 1), True)
        self.assertFalse(registry.slots[0]["indexed"])
        self.assertEqual(registry.register(self.row(3)), 2)

    def test_removed_cell_history_survives_checkpoint(self):
        registry = self.registry()
        registry.register(self.row(1))
        registry.remove(0, ("effect_area", 1))
        arena = dict(x=0, y=0, width=4, height=4, cell_masks=[0] * 16)
        restored = NativeQIRegistry(
            arena,
            registry.serialized_slots(),
            touched_cells=registry.serialized_cells(),
        )
        self.assertEqual(restored.snapshot().U(1, 1), frozenset())
        self.assertIsNone(restored.snapshot().U(2, 2))


if __name__ == "__main__":
    unittest.main()
