import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_targets import area_offsets, select_effect_targets


class DiagonalCrossTests(unittest.TestCase):
    def test_original_symmetric_asymmetric_and_negative_lists(self):
        rows = [
            ("crossDiag-h1b1-g1d1", {(0, 0), (-1, 1), (1, -1), (-1, -1), (1, 1)}),
            (
                "crossDiag-h2b2-g1d1",
                {(0, 0), (-1, 1), (1, -1), (-1, -1), (-2, -2), (1, 1), (2, 2)},
            ),
            (
                "crossDiag-h1b3-g4d2",
                {
                    (0, 0),
                    (-1, 1),
                    (-2, 2),
                    (-3, 3),
                    (-4, 4),
                    (1, -1),
                    (2, -2),
                    (-1, -1),
                    (1, 1),
                    (2, 2),
                    (3, 3),
                },
            ),
            ("crossDiag-h-1b-1-g-1d-1", {(0, 0)}),
        ]
        for description, expected in rows:
            effect = dict(area_class="anx", area_native=description)
            for direction in range(8):
                self.assertEqual(
                    area_offsets(
                        effect,
                        origin=(0, 0, 3),
                        reference=(3, 0, 9),
                        direction=direction,
                    ),
                    expected,
                )

    def test_actor_footprint_and_affiliation_on_diagonals(self):
        caster = SimpleNamespace(
            id=1, team=0, position=(0, 0, 0), hp=10, physical_radius=0
        )
        direct = SimpleNamespace(
            id=2, team=1, position=(1, 1, 9), hp=10, physical_radius=0
        )
        footprint = SimpleNamespace(
            id=3, team=1, position=(2, 1, 9), hp=10, physical_radius=1
        )
        outside = SimpleNamespace(
            id=4, team=1, position=(2, 0, 0), hp=10, physical_radius=0
        )
        effect = dict(area_class="anx", area_native="crossDiag-h1b1-g1d1")
        selected = select_effect_targets(
            effect,
            caster,
            (0, 0, 0),
            (caster, direct, footprint, outside),
            relations={"enemy"},
            native_radius=True,
        )
        self.assertEqual(tuple(actor.id for actor in selected), (2, 3))


if __name__ == "__main__":
    unittest.main()
