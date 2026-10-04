"""Vectors verified against aAS/aBA in the real client JAR."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_displacement import displacement_geometry


class DisplacementFacingTests(unittest.TestCase):
    def geometry(self, family, mode, source, target):
        return displacement_geometry(
            {"effect_class": family, "parameters": [2, 0, 0, 0, mode, 0]},
            1,
            source=source,
            target=target,
            cell=(10, 10, 0),
        )

    def test_push_caster_facing_all_native_directions(self):
        expected = [(0, -1), (1, 0), (1, 0), (0, 1), (0, 1), (-1, 0), (-1, 0), (0, -1)]
        target = SimpleNamespace(position=(4, 0, 0))
        for direction, vector in enumerate(expected):
            source = SimpleNamespace(position=(0, 0, 0), direction=direction)
            self.assertEqual(self.geometry(300, 7, source, target)["vector"], vector)

    def test_forced_override_and_native_null_fallback(self):
        source = SimpleNamespace(position=(0, 0, 0))
        target = SimpleNamespace(
            position=(4, 0, 0), direction=1, native_forced_direction=None
        )
        for family in (300, 301):
            self.assertEqual(
                self.geometry(family, 4, source, target)["vector"], (-1, 0)
            )
            target.native_forced_direction = 7
            self.assertEqual(self.geometry(family, 4, source, target)["vector"], (0, 1))
            target.native_forced_direction = None

    def test_unknown_override_and_random_still_reject(self):
        source = SimpleNamespace(position=(0, 0, 0), direction=1)
        target = SimpleNamespace(position=(4, 0, 0), direction=1)
        with self.assertRaisesRegex(ValueError, "pGJ"):
            self.geometry(300, 4, source, target)
        with self.assertRaisesRegex(ValueError, "random"):
            self.geometry(300, 6, source, target)


if __name__ == "__main__":
    unittest.main()
