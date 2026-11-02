"""Native Door coordinates preserve integral JSON numbers without truncation."""
import unittest

from wakfu_server.combat_sn_path import NativeSnColumns
from wakfu_server.dungeon_native_door_collision import native_blocking_cells


def columns():
    return NativeSnColumns(
        {
            "schema": "native-Sn-Vy-columns-v1",
            "map_id": 716,
            "source_sha256": "a" * 64,
            "chunks": [
                {
                    "x": 0,
                    "y": 18,
                    "width": 18,
                    "height": 18,
                    "columns": [[5, 29, [[0, 0, 0, 0, 1, False]]]],
                }
            ],
        },
        map_id=716,
        source_sha256="a" * 64,
    )


class NativeDoorIntegralPositionTests(unittest.TestCase):
    def test_integer_position_retains_native_column(self):
        self.assertEqual(
            native_blocking_cells(716, [5, 29, 0], columns=columns()),
            frozenset({(5, 29, 0)}),
        )

    def test_integral_floats_normalize_without_mutating_source(self):
        position = [5.0, 29.0, 0.0]
        actual = native_blocking_cells(716, position, columns=columns())
        self.assertEqual(actual, frozenset({(5, 29, 0)}))
        self.assertTrue(all(type(value) is int for point in actual for value in point))
        self.assertTrue(all(type(value) is float for value in position))

    def test_boolean_coordinates_are_rejected(self):
        for axis in range(3):
            for boolean in (True, False):
                position = [5, 29, 0]
                position[axis] = boolean
                with self.subTest(axis=axis, value=boolean), self.assertRaises(
                    ValueError
                ):
                    native_blocking_cells(716, position, columns=columns())

    def test_fractional_coordinates_are_not_truncated_or_rounded(self):
        for value in (5.5, 5.000000000000001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                native_blocking_cells(716, [value, 29, 0], columns=columns())

    def test_nan_coordinates_are_rejected(self):
        with self.assertRaises(ValueError):
            native_blocking_cells(716, [float("nan"), 29, 0], columns=columns())

    def test_infinite_coordinates_are_rejected(self):
        for value in (float("inf"), -float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                native_blocking_cells(716, [value, 29, 0], columns=columns())

    def test_integral_coordinates_still_obey_native_ranges(self):
        for position in (
            [2**31, 29, 0],
            [float(2**31), 29, 0],
            [-(2**31) - 1, 29, 0],
            [5, 29, 32768.0],
            [5, 29, -32769.0],
            [10**1000, 29, 0],
        ):
            with self.subTest(position=position), self.assertRaises(ValueError):
                native_blocking_cells(716, position, columns=columns())


if __name__ == "__main__":
    unittest.main()
