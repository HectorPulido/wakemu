import unittest

from wakfu_server.combat_qi_surfaces import NativeQISurfaces
from wakfu_server.combat_qi_snapshot import NativeQISnapshot
from wakfu_server.combat_wire import arena, topology, decode_topology


class UnavailableNativeSurfaceTests(unittest.TestCase):
    def test_native_population_excludes_missing_height_without_inventing_border(self):
        source = NativeQISurfaces(
            dict(
                schema="native-QI-Vy-columns-v1",
                map_id=448,
                source_sha256="a" * 64,
                chunks=[
                    dict(
                        x=0,
                        y=0,
                        width=3,
                        height=2,
                        columns=[
                            [0, 0, [[8, 0]]],
                            [1, 0, [[-32768, -1]]],
                            [2, 0, [[4, -1]]],
                            [1, 1, [[-32768, -1]]],
                            [2, 1, [[9, 0]]],
                        ],
                    )
                ],
            ),
            map_id=448,
            source_sha256="a" * 64,
        )
        cells = [(0, 0, 8), (2, 1, 9)]
        args = (448, 7, cells, {0: cells[0], 1: cells[1]})
        kwargs = dict(
            surface_indices={(0, 0): 0, (2, 1): 0},
            border_cells=[cells[0]],
            gap_surface_indices={(2, 0): 0, (1, 1): 0},
        )
        old = arena(*args, **kwargs)
        candidate = arena(*args, **kwargs, native_surfaces=source)
        decoded = decode_topology(topology(candidate))
        qi = NativeQISnapshot(decoded)
        # Actual QI.Q is the predicate used by the original bdY population;
        # QI.R is the native unavailable-cell predicate used by local scopes.
        for xy in ((1, 0), (0, 1), (1, 1)):
            self.assertFalse(qi.Q(*xy))
            self.assertFalse(qi.R(*xy))
            self.assertFalse(qi.P(*xy))
        # The native battleground consumer requires exact QI.P equality.
        self.assertEqual(
            {(x, y) for y in range(2) for x in range(3) if qi.P(x, y)}, {(0, 0)}
        )
        from wakfu_server.combat_casting_los import native_qi_h

        self.assertFalse(
            native_qi_h(
                qi,
                1,
                0,
                8,
                ordered_slots=lambda x, y: (),
                visibility=lambda slot: False,
                ignored=frozenset(),
            )
        )
        self.assertEqual(decoded["cell_flags"], old["cell_flags"])
        for xy in ((0, 0), (2, 0), (2, 1)):
            offset = xy[1] * 3 + xy[0]
            self.assertEqual(decoded["cell_masks"][offset], old["cell_masks"][offset])
            self.assertEqual(qi.Q(*xy), xy != (0, 0))
        self.assertEqual(old["cell_masks"][1], 256)

    def test_foreign_map_surface_authority_is_rejected(self):
        source = NativeQISurfaces(
            dict(
                schema="native-QI-Vy-columns-v1",
                map_id=448,
                source_sha256="a" * 64,
                chunks=[],
            ),
            map_id=448,
            source_sha256="a" * 64,
        )
        with self.assertRaisesRegex(ValueError, "matching native Vy"):
            arena(
                449,
                7,
                [(0, 0, 8), (1, 0, 8)],
                {0: (0, 0, 8), 1: (1, 0, 8)},
                native_surfaces=source,
            )


if __name__ == "__main__":
    unittest.main()
