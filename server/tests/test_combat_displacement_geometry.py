"""Offline geometry contracts; coordinates are declared inputs, not native maps."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_displacement_geometry import (
    FAMILIES,
    cardinal_vector,
    _facing_vector,
    displacement_geometry,
)


class DisplacementGeometryTests(unittest.TestCase):
    def setUp(self):
        self.source = SimpleNamespace(position=(0, 0, 0), direction=1)
        self.target = SimpleNamespace(
            position=(3, 0, 0), direction=1, native_forced_direction=None
        )

    def geometry(self, family, parameters, **kwargs):
        return displacement_geometry(
            {"effect_class": family, "parameters": parameters},
            kwargs.pop("level", 1),
            source=self.source,
            target=self.target,
            cell=kwargs.pop("cell", (5, 0, 0)),
            **kwargs,
        )

    def test_new_native_3217_4536_root118972_parameter_witness(self):
        # Exported root118972 is class300, parameters[1,0,0,0]. This is
        # geometry coverage, not ownership, cost, targeting or admission proof.
        result = self.geometry(300, [1.0, 0.0, 0.0, 0.0])
        self.assertIs(result["actor"], self.target)
        self.assertEqual(
            result,
            dict(
                actor=self.target,
                distance=1,
                vector=(1, 0),
                stop=None,
                loss_ap=False,
                collision_reactions=True,
            ),
        )
        self.assertEqual(self.source.position, (0, 0, 0))
        self.assertEqual(self.target.position, (3, 0, 0))

    def test_all_families_and_native_parameter_growth(self):
        self.assertEqual(set(FAMILIES), {300, 301, 302, 340, 331, 305, 422})
        push = self.geometry(300, [1, 0.5], level=2)
        self.assertEqual((push["distance"], push["loss_ap"]), (2, True))
        pull = self.geometry(301, [4, 0])
        self.assertEqual(
            (pull["vector"], pull["stop"], pull["loss_ap"]), ((-1, 0), (1, 0), False)
        )
        away = self.geometry(331, [2, 0])
        self.assertIs(away["actor"], self.source)
        self.assertEqual(
            (away["vector"], away["collision_reactions"]), ((-1, 0), False)
        )
        approach = self.geometry(305, [])
        self.assertEqual(
            (
                approach["distance"],
                approach["vector"],
                approach["stop"],
                approach["loss_ap"],
            ),
            (5, (1, 0), (5, 0), False),
        )
        for family, actor in ((302, self.source), (340, self.target)):
            self.assertEqual(
                self.geometry(family, []),
                dict(
                    actor=actor,
                    force=False,
                    carried=False,
                    check_cells=True,
                    destination=(5, 0, 0),
                ),
            )
            self.assertEqual(
                self.geometry(family, [0, 0, 1, 0, 1, 0, 0, 0]),
                dict(
                    actor=actor,
                    force=True,
                    carried=True,
                    check_cells=False,
                    destination=(5, 0, 0),
                ),
            )
        self.assertEqual(
            self.geometry(422, [1, 0]),
            dict(source=self.source, target=self.target, force=True),
        )
        self.assertFalse(self.geometry(422, [])["force"])

    def test_native_random_push_draws_once_and_pull_never_draws(self):
        for draw, expected in enumerate(((0, -1), (-1, 0), (1, 0), (0, 1)), 1):
            calls = []
            result = self.geometry(
                300,
                [2, 0, 0, 0, 6, 0],
                draw_direction=lambda: calls.append(draw) or draw,
            )
            self.assertEqual(result["vector"], expected)
            self.assertEqual(calls, [draw])
        for mode in (6, 7, -1, 99):
            result = self.geometry(
                301,
                [2, 0, 0, 0, mode, 0],
                draw_direction=lambda: self.fail("Pull drew RNG"),
            )
            self.assertEqual(result["vector"], (1, 0))
        with self.assertRaisesRegex(ValueError, "transaction-owned"):
            self.geometry(300, [2, 0, 0, 0, 6, 0])
        for invalid in (True, None, 0, 5):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ValueError, "direction draw"
            ):
                self.geometry(300, [2, 0, 0, 0, 6, 0], draw_direction=lambda: invalid)

    def test_native_facing_and_float32_sector_boundaries(self):
        expected = ((0, -1), (1, 0), (1, 0), (0, 1), (0, 1), (-1, 0), (-1, 0), (0, -1))
        for direction, vector in enumerate(expected):
            self.source.direction = direction
            self.assertEqual(_facing_vector(self.source), vector)
        self.assertEqual(cardinal_vector(0, 0), (0, 0))
        for delta, vector in (
            ((1, 1), (1, 0)),
            ((1, -1), (0, -1)),
            ((-1, 1), (0, 1)),
            ((-1, -1), (-1, 0)),
        ):
            self.assertEqual(cardinal_vector(*delta), vector)
        self.target.native_forced_direction = 7
        self.assertEqual(_facing_vector(self.target, forced=True, reverse=True), (0, 1))
        self.target.native_forced_direction = None
        self.assertEqual(
            _facing_vector(self.target, forced=True, reverse=True), (-1, 0)
        )
        with self.assertRaisesRegex(ValueError, "pGJ"):
            _facing_vector(self.source, forced=True)
        self.source.direction = True
        with self.assertRaisesRegex(ValueError, "orientation"):
            _facing_vector(self.source)

    def test_native_bounds_and_context_rejections(self):
        for distance in (0, 6552):
            self.assertEqual(self.geometry(300, [distance, 0])["distance"], distance)
        for distance in (-1, 6553):
            with self.assertRaisesRegex(ValueError, "distance"):
                self.geometry(300, [distance, 0])
        for family, parameters in (
            (300, []),
            (331, [1, 0, 1, 0]),
            (305, [1, 0] * 3),
            (302, [0, 0] * 5),
            (422, [0, 0] * 2),
        ):
            with self.subTest(family=family), self.assertRaises(ValueError):
                self.geometry(family, parameters)
        with self.assertRaisesRegex(ValueError, "wrapped actor"):
            self.geometry(302, [1, 0])
        self.assertIs(
            self.geometry(302, [1, 0], teleport_recipient_is_fighter=True)["actor"],
            self.source,
        )
        with self.assertRaisesRegex(ValueError, "signed short"):
            self.geometry(300, [1, 0], level=32768)


if __name__ == "__main__":
    unittest.main()
