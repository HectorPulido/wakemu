import copy
import unittest
from wakfu_server.combat_microbot_path import NativeMicrobotPathProjection
from wakfu_server.combat_qi_snapshot import NativeQISnapshot, RegisteredObstacle
from wakfu_server.combat_qi_surfaces import NativeQISurfaces
from wakfu_server.combat_sn_path import NativeSnColumns


class NativeMicrobotPathTests(unittest.TestCase):
    def projection(self, *, middle_z=0, middle_blocked=False):
        qi = NativeQISnapshot(
            dict(x=0, y=0, width=3, height=1, cell_masks=[0, 0, 0]),
            obstacles=[RegisteredObstacle(7, 1, 0, 0)],
        )
        physical = [
            [
                x,
                0,
                [
                    [
                        middle_z if x == 1 else 0,
                        -1 if x == 1 and middle_blocked else 0,
                        0,
                        0,
                        0,
                        False,
                    ]
                ],
            ]
            for x in range(3)
        ]
        columns = NativeSnColumns(
            dict(
                schema="native-Sn-Vy-columns-v1",
                map_id=1134,
                source_sha256="a" * 64,
                chunks=[dict(x=0, y=0, width=18, height=18, columns=physical)],
            ),
            map_id=1134,
            source_sha256="a" * 64,
        )
        surfaces = NativeQISurfaces(
            dict(
                schema="native-QI-Vy-columns-v1",
                map_id=1134,
                source_sha256="b" * 64,
                chunks=[
                    dict(
                        x=0,
                        y=0,
                        width=3,
                        height=1,
                        columns=[
                            [x, 0, [[middle_z if x == 1 else 0, 0]]] for x in range(3)
                        ],
                    )
                ],
            ),
            map_id=1134,
            source_sha256="b" * 64,
        )
        return NativeMicrobotPathProjection(qi, surfaces, columns)

    def test_native_rail_path_ignores_dynamic_occupancy_without_mutating_qi(self):
        projection = self.projection()
        before = copy.deepcopy(vars(projection.qi))
        self.assertEqual(projection.qi.U(1, 0), frozenset({7}))
        self.assertTrue(projection.segment_is_passable((0, 0, 0), (2, 0, 0)))
        self.assertEqual(vars(projection.qi), before)

    def test_native_rail_configuration_preserves_physical_blocks_and_jump_four(self):
        self.assertFalse(
            self.projection(middle_blocked=True).segment_is_passable(
                (0, 0, 0), (2, 0, 0)
            )
        )
        self.assertTrue(
            self.projection(middle_z=4).segment_is_passable((0, 0, 0), (2, 0, 0))
        )
        self.assertFalse(
            self.projection(middle_z=5).segment_is_passable((0, 0, 0), (2, 0, 0))
        )

    def test_network_cell_altitude_uses_actual_mask_selected_qi_x(self):
        projection = self.projection(middle_z=4)
        self.assertEqual(projection.surface_z(1, 0), 4)
        self.assertFalse(projection.segment_is_passable((0, 0, 0), (2, 1, 0)))


if __name__ == "__main__":
    unittest.main()
