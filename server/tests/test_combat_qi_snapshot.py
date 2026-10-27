import unittest
from wakfu_server.combat_qi_snapshot import NativeQISnapshot, RegisteredObstacle


class NativeQISnapshotTests(unittest.TestCase):
    def test_frozen_masks_share_only_terrain_and_preserve_mutable_validation(self):
        from copy import deepcopy
        import json
        from types import SimpleNamespace
        from wakfu_server.combat_geometry_snapshot import (
            freeze_terrain,
            source_snapshot,
        )
        from wakfu_server.fight_checkpoint_store import _plain

        raw = [0, 128]
        fight = SimpleNamespace(
            walkable={(10, 20, 0), (11, 20, 0)},
            edges=None,
            actors={},
            native_qi_snapshot=dict(x=10, y=20, width=2, height=1, cell_masks=raw),
        )
        before = source_snapshot(fight)
        freeze_terrain(fight)
        private = deepcopy(fight)
        original_qi = NativeQISnapshot(fight.native_qi_snapshot, obstacles=[])
        private_qi = NativeQISnapshot(
            private.native_qi_snapshot, obstacles=[RegisteredObstacle(1, 10, 20, 0)]
        )
        self.assertIs(original_qi.masks, private_qi.masks)
        self.assertIsNot(original_qi.occupancy, private_qi.occupancy)
        self.assertIsNone(original_qi.U(10, 20))
        self.assertEqual(private_qi.U(10, 20), frozenset({1}))
        self.assertEqual(_plain(source_snapshot(fight)), before)
        self.assertEqual(
            json.loads(json.dumps(_plain(fight.native_qi_snapshot)))["cell_masks"], raw
        )
        # A mutable caller remains detached, and its later edits are validated.
        raw[0] = True
        self.assertFalse(original_qi.P(10, 20))
        with self.assertRaises(ValueError):
            self.snapshot(raw)
        with self.assertRaises(TypeError):
            private_qi.masks[0] = 128
        from wakfu_server.combat_invariant_spatial import check_legacy_topology

        findings = []
        check_legacy_topology(
            dict(
                native_qi_snapshot=fight.native_qi_snapshot,
                native_qi_byte_topology={},
                native_qi_touched_cells=[],
            ),
            [],
            lambda *row: findings.append(row),
            lambda *row: findings.append(row),
            [],
        )
        self.assertEqual(findings, [])
        for replacement in (
            dict(width=1),
            dict(height=True),
            dict(x=1 << 31),
            dict(cell_masks=[0, 65535]),
            dict(cell_masks=(0, 1.0)),
        ):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                NativeQISnapshot(dict(fight.native_qi_snapshot, **replacement))

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
