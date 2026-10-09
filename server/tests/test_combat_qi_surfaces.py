import unittest

from wakfu_server.combat_qi_snapshot import NativeQISnapshot
from wakfu_server.combat_qi_surfaces import NativeQISurfaces, NativeSurface


class NativeQISurfacesTests(unittest.TestCase):
    MAP_ID = 1134
    SOURCE = "a" * 64

    def provider(self, chunks):
        data = {
            "schema": "native-QI-Vy-columns-v1",
            "map_id": self.MAP_ID,
            "source_sha256": self.SOURCE,
            "chunks": chunks,
        }
        return NativeQISurfaces(data, map_id=self.MAP_ID, source_sha256=self.SOURCE)

    def chunk(self, columns, *, x=10, y=20, width=1, height=1):
        return {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "columns": columns,
        }

    def qi(self, masks, *, x=10, y=20, width=None, height=1):
        width = len(masks) if width is None else width
        return NativeQISnapshot(
            {"x": x, "y": y, "width": width, "height": height, "cell_masks": masks}
        )

    def test_surface_selection_uses_mask_index_and_preserves_native_order(self):
        surfaces = self.provider([self.chunk([[10, 20, [[-2, 3], [4, 5], [6, -2]]]])])
        qi = self.qi([0x100 | 2])

        self.assertEqual(surfaces.i(qi, 10, 20, 6), NativeSurface(6, -2))
        self.assertTrue(surfaces.j(qi, 10, 20, 6))
        # A matching altitude at another index cannot override the selected surface.
        self.assertIsNone(surfaces.i(qi, 10, 20, 4))
        self.assertFalse(surfaces.j(qi, 10, 20, 4))

    def test_only_exact_negative_one_is_blocked_and_mask_block_bit_does_not_block(self):
        surfaces = self.provider([self.chunk([[10, 20, [[1, -1], [2, -7], [3, 9]]]])])

        self.assertFalse(surfaces.j(self.qi([0x100]), 10, 20, 1))
        self.assertTrue(surfaces.j(self.qi([0x100 | 1]), 10, 20, 2))

    def test_index_outside_column_count_and_first_empty_column_return_none(self):
        surfaces = self.provider(
            [self.chunk([[10, 20, [[0, 1]]], [11, 20, []]], width=2)]
        )
        qi = self.qi([1, 0], width=2)

        self.assertIsNone(surfaces.i(qi, 10, 20, 0))
        self.assertFalse(surfaces.j(qi, 10, 20, 0))
        self.assertIsNone(surfaces.i(qi, 11, 20, 0))
        self.assertFalse(surfaces.j(qi, 11, 20, 0))

    def test_first_matching_empty_chunk_does_not_fall_through_to_later_chunk(self):
        surfaces = self.provider(
            [
                self.chunk([]),
                self.chunk([[10, 20, [[0, 7]]]]),
            ]
        )
        qi = self.qi([0])

        self.assertIsNone(surfaces.i(qi, 10, 20, 0))
        self.assertFalse(surfaces.j(qi, 10, 20, 0))

    def test_out_of_bounds_and_missing_chunk_are_absent(self):
        surfaces = self.provider([self.chunk([[10, 20, [[0, 0]]]])])
        qi = self.qi([0], width=1)

        self.assertIsNone(surfaces.i(qi, 9, 20, 0))
        self.assertIsNone(surfaces.i(qi, 11, 20, 0))
        self.assertTrue(surfaces.j(qi, 10, 20, 0))

    def test_missing_or_mismatched_provenance_is_rejected(self):
        valid = {
            "schema": "native-QI-Vy-columns-v1",
            "map_id": self.MAP_ID,
            "source_sha256": self.SOURCE,
            "chunks": [],
        }
        cases = (
            ({**valid, "source_sha256": "b" * 64}, self.MAP_ID, self.SOURCE),
            (valid, 999, self.SOURCE),
            ({**valid, "schema": "unknown"}, self.MAP_ID, self.SOURCE),
            (valid, self.MAP_ID, "missing"),
        )
        for data, map_id, source_hash in cases:
            with self.subTest(map_id=map_id, source_hash=source_hash):
                with self.assertRaisesRegex(ValueError, "provenance"):
                    NativeQISurfaces(data, map_id=map_id, source_sha256=source_hash)

    def test_malformed_ordered_columns_and_signed_surface_values_reject(self):
        malformed = (
            [[10, 20, [[32768, 0]]]],
            [[10, 20, [[0, -129]]]],
            [[11, 20, [[0, 0]]]],
        )
        for columns in malformed:
            with self.subTest(columns=columns):
                with self.assertRaises(ValueError):
                    self.provider([self.chunk(columns)])
        with self.assertRaisesRegex(ValueError, "columns"):
            self.provider([self.chunk(None)])


if __name__ == "__main__":
    unittest.main()

    def test_X_returns_selected_height_and_native_short_sentinel(self):
        surfaces = self.provider(
            [
                self.chunk([[10, 20, [[-2, -1], [4, 3]]]]),
                self.chunk([[10, 20, [[8, 0], [9, 0], [10, 0]]]]),
            ]
        )
        self.assertEqual(surfaces.X(self.qi([0x100 | 1]), 10, 20), 4)
        self.assertEqual(surfaces.X(self.qi([2]), 10, 20), -32768)
        self.assertEqual(surfaces.X(self.qi([0]), 10, 20), -2)
        with self.assertRaises(ValueError):
            surfaces.X(self.qi([0]), 9, 20)
