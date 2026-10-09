import unittest
from wakfu_server.combat_qi_snapshot import NativeQISnapshot, RegisteredObstacle


class NativeQISnapshotTests(unittest.TestCase):
    def snapshot(self, masks, **kwargs):
        return NativeQISnapshot(
            dict(x=10, y=20, width=len(masks), height=1, cell_masks=masks), **kwargs
        )

    def test_border_uses_bit_and_exact_sentinel_not_walkability(self):
        qi = self.snapshot([0, 128, 256, 384, -257, -1])
        self.assertEqual(
            [qi.P(x, 20) for x in range(10, 16)],
            [False, True, False, True, False, True],
        )
        self.assertFalse(qi.P(9, 20))
        self.assertFalse(qi.P(10, 21))
        self.assertEqual(
            [qi.R(x, 20) for x in range(10, 16)], [True, True, True, True, False, False]
        )
        self.assertFalse(qi.Q(11, 20))
        self.assertTrue(qi.Q(12, 20))

    def test_bounds_preserve_blocked_rectangle_cells(self):
        qi = self.snapshot([256])
        self.assertTrue(qi.aK(10, 20))
        self.assertTrue(qi.R(10, 20))
        self.assertFalse(qi.aK(11, 20))

    def test_path_option_z_uses_wrapped_index_and_bits_768_not_aK(self):
        qi = NativeQISnapshot(
            dict(x=10, y=20, width=2, height=2, cell_masks=[768, 256, 512, 128])
        )
        self.assertFalse(qi.aK(12, 19))
        self.assertTrue(qi.Z(12, 19))  # (dy * width) + dx aliases index zero.
        self.assertTrue(qi.Z(13, 19))  # Aliased index one has bit 256.
        self.assertTrue(qi.Z(10, 21))  # Mask tests either bit in native 768.
        self.assertFalse(qi.Z(11, 21))
        self.assertTrue(qi.Z(10, -(1 << 31) + 20))  # Java int multiply wraps to zero.
        with self.assertRaisesRegex(ValueError, "coordinate"):
            qi.Z(1 << 31, 20)

    def test_unknown_population_differs_from_complete_absent_entry(self):
        with self.assertRaisesRegex(ValueError, "registration"):
            self.snapshot([0]).U(10, 20)
        self.assertIsNone(self.snapshot([0], obstacles=[]).U(10, 20))
        self.assertEqual(self.snapshot([0]).U(9, 20), frozenset())

    def test_obstacle_ids_square_footprint_and_overlaps(self):
        qi = NativeQISnapshot(
            dict(x=0, y=0, width=3, height=3, cell_masks=[0] * 9),
            obstacles=[RegisteredObstacle(5, 1, 1, 1), RegisteredObstacle(9, 0, 0, 0)],
        )
        self.assertEqual(qi.U(0, 0), frozenset({5, 9}))
        self.assertEqual(qi.U(2, 2), frozenset({5}))
        self.assertEqual(qi.U(3, 3), frozenset())

    def test_missing_mask_and_duplicate_obstacle_authority_reject(self):
        for masks in ([True], [65535], []):
            with self.assertRaises(ValueError):
                self.snapshot(masks)
        with self.assertRaisesRegex(ValueError, "obstacle"):
            self.snapshot([0], obstacles=[RegisteredObstacle(1, 10, 20, 0)] * 2)

    def test_footprint_overflow_and_outside_point_registration_reject(self):
        for obstacle in (
            RegisteredObstacle(1, (1 << 31) - 1, 20, 1),
            RegisteredObstacle(1, -(1 << 31), 20, 1),
            RegisteredObstacle(1, 9, 20, 0),
            RegisteredObstacle(1, 9, 20, -1),
        ):
            with self.subTest(obstacle=obstacle):
                with self.assertRaisesRegex(ValueError, "domain|bounds"):
                    self.snapshot([0], obstacles=[obstacle])
