"""Original anc.b/amX.a isotropic footprint matrix; no spell/class exceptions."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_targets import select_effect_targets


class NativeIsotropicFootprintTests(unittest.TestCase):
    def selected(
        self, kind, description, x, y, radius, *, native=True, relation="enemy"
    ):
        caster = SimpleNamespace(
            id=7, team=0, position=(0, 0, 0), hp=100, physical_radius=0
        )
        actor = SimpleNamespace(
            id=-7, team=1, position=(x, y, 17), hp=100, physical_radius=radius
        )
        return bool(
            select_effect_targets(
                dict(area_class=kind, area_native=description),
                caster,
                (0, 0, -20),
                (actor,),
                relations={relation},
                native_radius=native,
            )
        )

    def test_original_point_circle_ring_matrix(self):
        rows = (
            (0, 0, 0),
            (1, 0, 0),
            (1, 0, 1),
            (2, 0, 1),
            (0, 0, 1),
            (2, 2, 1),
            (1, 0, -1),
        )
        for kind, text, expected in (
            ("anD", "point", (True, False, True, False, True, False, False)),
            ("anu", "circle-1", (True, True, True, True, True, False, True)),
            ("anH", "ring-1-1", (False, True, True, True, True, False, True)),
        ):
            for row, accepted in zip(rows, expected):
                with self.subTest(shape=text, actor=row):
                    self.assertEqual(self.selected(kind, text, *row), accepted)

    def test_square_footprint_and_cross_holes(self):
        self.assertTrue(self.selected("anD", "point", 1, 1, 1))
        self.assertTrue(self.selected("anw", "cross-h1b1-g1d1", 2, 1, 1))
        self.assertTrue(self.selected("any", "crossRing-1-1", 0, 0, 1))
        self.assertFalse(self.selected("any", "crossRing-1-1", 0, 0, 0))

    def test_null_selector_centre_route_stays_distinct(self):
        self.assertFalse(self.selected("anD", "point", 1, 0, 1, native=False))
        self.assertTrue(self.selected("anD", "point", 0, 0, None, native=False))

    def test_footprint_does_not_bypass_relation(self):
        self.assertFalse(self.selected("anD", "point", 1, 0, 1, relation="ally"))

    def test_unknown_or_invalid_native_radius_is_not_zero(self):
        for radius in (None, True, 128, -129):
            with self.subTest(radius=radius), self.assertRaises(ValueError):
                self.selected("anD", "point", 0, 0, radius)

    def test_fcE_selector_route_uses_physical_footprint(self):
        from wakfu_server.combat_effect_targets import select_native_effect_targets

        caster = SimpleNamespace(
            id=7, team=0, position=(0, 0, 0), hp=100, physical_radius=0
        )
        actor = SimpleNamespace(
            id=-7, team=1, position=(1, 0, 17), hp=100, physical_radius=1
        )
        context = {
            identity: dict(
                bEe=True,
                is_amO=True,
                is_Qq=False,
                is_eGj=True,
                is_eHH=False,
                bcR=False,
                bcN=0,
                UNTARGETTABLE_BY_OTHER=False,
            )
            for identity in (7, -7)
        }
        definition = dict(
            area_class="anD",
            area_native="point",
            native_target_selector={"class": "fcE", "mask": 9},
        )
        selected = select_native_effect_targets(
            definition, caster, (0, 0, -20), (actor,), native_context=context
        )
        self.assertEqual([a.id for a in selected], [-7])
        definition["native_target_selector"] = None
        self.assertEqual(
            select_native_effect_targets(
                definition, caster, (0, 0, -20), (actor,), native_context=context
            ),
            (),
        )
