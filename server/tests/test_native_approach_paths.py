"""Probe path goals obey native masks and actual reachable surface height."""

import unittest

from tools.native_approach_paths import source_path


class NativeApproachPathTests(unittest.TestCase):
    def setUp(self):
        self.document = dict(
            map_id=527,
            profile=dict(height=6, movement_type=0, jump_capacity=4, native_class="Sm"),
            client_sha256="explicit fixture",
            topology_sha256="explicit fixture",
            cells=[[0, 0, 0], [1, 0, 0], [1, 1, -4], [0, 1, -4], [0, 1, 0]],
            edges=[
                [[0, 0, 0], [1, 0, 0]],
                [[1, 0, 0], [1, 1, -4]],
                [[1, 1, -4], [0, 1, -4]],
            ],
        )

    def test_zero_mask_uses_reachable_exact_xy_not_the_nearby_visual_height(self):
        # Same X/Y has a ground surface but it is not reachable. The native
        # underground approach is reached through the original ramp edges.
        source = dict(
            map_id=527, x=0.0, y=1.0, z=20.0, approach_mask=0, approach_positions=[]
        )
        result = source_path(self.document, source, (0, 0, 0))
        self.assertEqual(
            result, dict(goal=(0, 1, -4), path=((1, 0, 0), (1, 1, -4), (0, 1, -4)))
        )

    def test_nonzero_mask_only_accepts_exported_native_cells_and_rejects_combat_profile(
        self,
    ):
        source = dict(
            map_id=527,
            x=0,
            y=1,
            z=20,
            approach_mask=8,
            approach_positions=[dict(x=1, y=1, z=-4)],
        )
        self.assertEqual(
            source_path(self.document, source, (0, 0, 0))["goal"], (1, 1, -4)
        )
        source["approach_positions"] = [dict(x=0, y=1, z=0)]
        with self.assertRaisesRegex(ValueError, "No native player path"):
            source_path(self.document, source, (0, 0, 0))
        self.document["profile"]["height"] = 3
        with self.assertRaisesRegex(ValueError, "original player export"):
            source_path(self.document, source, (0, 0, 0))
