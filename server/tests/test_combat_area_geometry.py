import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from wakfu_server.combat.combat_area_geometry import (
    oriented_area_offsets,
    native_area_contains,
)
from wakfu_server.combat.combat_effect_targets import (
    select_native_effect_targets,
    area_offsets,
)
from wakfu_server.combat.combat_group_cells import group_cells
from wakfu_server.combat.combat_native_area_metadata import (
    merge_native_point_areas,
    native_point_area_metadata,
)


class NativeDirectionalAreaTests(unittest.TestCase):
    def test_compact_native_metadata_identity_and_order(self):
        rows = native_point_area_metadata()
        self.assertEqual(len(rows), 5343)
        for reference, row in rows.items():
            effect = {
                key: row[key] for key in ("effect_class", "area_class", "area_native")
            }
            merged = merge_native_point_areas({reference: effect})[reference]
            self.assertEqual(merged["native_area_points"], row["native_area_points"])
            self.assertNotIn("native_area_points", effect)
        reference, row = next(iter(rows.items()))
        wrong = dict(row, effect_class=row["effect_class"] + 1)
        with self.assertRaisesRegex(ValueError, "identity"):
            merge_native_point_areas({reference: wrong})
        with self.assertRaisesRegex(ValueError, "Missing"):
            merge_native_point_areas({"unexported": dict(area_class="anE")})

    def test_point_area_routes_ordered_cells_and_actor_membership(self):
        effect = dict(
            area_class="anE",
            area_native="forme à base de points",
            native_area_points=[[1, 0], [0, 1], [0, -1], [1, 0]],
        )
        caster = SimpleNamespace(id=1, position=(0, 0, 0), direction=1)
        fight = SimpleNamespace(
            actors={1: caster}, walkable={(3, 0, 2), (2, 1, 4), (2, -1, 6)}
        )
        self.assertEqual(
            group_cells(fight, effect, (2, 0, 0), caster_id=1),
            ((3, 0, 2), (2, 1, 4), (2, -1, 6)),
        )
        self.assertTrue(
            native_area_contains(effect, origin=(2, 0), reference=(0, 0), point=(3, 0))
        )
        self.assertFalse(
            native_area_contains(effect, origin=(2, 0), reference=(0, 0), point=(2, 0))
        )

    def test_native_108_orientations_match_enumeration_and_actor_membership(self):
        rows = json.loads(
            (
                Path(__file__).parents[1] / "protocol/native-oriented-area-fixture.json"
            ).read_text()
        )
        self.assertEqual(len(rows), 234)
        for row in rows:
            effect = dict(area_class=row["class"], area_native=row["native"])
            if row["class"] in ("anE", "anJ"):
                effect["native_area_points"] = row["native_area_points"]
            reference = tuple(-v for v in row["vector"])
            args = dict(
                origin=(0, 0, 99),
                reference=reference,
                direction=row["fallback_direction"],
            )
            with self.subTest(
                area=row["native"],
                vector=row["vector"],
                direction=row["fallback_direction"],
            ):
                self.assertEqual(
                    list(oriented_area_offsets(effect, **args)),
                    [tuple(v) for v in row["cells"]],
                )
                membership = {
                    (x, y)
                    for x in range(-6, 7)
                    for y in range(-6, 7)
                    if native_area_contains(effect, point=(x, y, -99), **args)
                }
                self.assertEqual(membership, {tuple(v) for v in row["membership"]})
                for radius, expected in row["radius_memberships"].items():
                    membership = {
                        (x, y)
                        for x in range(-6, 7)
                        for y in range(-6, 7)
                        if native_area_contains(
                            effect, point=(x, y, -99), radius=int(radius), **args
                        )
                    }
                    self.assertEqual(membership, {tuple(v) for v in expected})

    def test_diagonal_self_facing_keeps_native_actor_cell_difference(self):
        effect = dict(area_class="anI", area_native="t-0-2")
        caster = SimpleNamespace(
            id=1, team=0, position=(0, 0, 0), hp=10, physical_radius=0, direction=0
        )
        actors = [
            caster,
            SimpleNamespace(
                id=2, team=0, position=(1, -1, 9), hp=10, physical_radius=0
            ),
            SimpleNamespace(
                id=3, team=1, position=(2, -2, 0), hp=10, physical_radius=0
            ),
        ]
        effect["native_target_selector"] = dict(**{"class": "fcE"}, mask=1)
        contexts = {
            a.id: dict(bEe=True, is_Qq=False, is_eGj=False, is_eHH=False)
            for a in actors
        }
        self.assertEqual(
            [
                a.id
                for a in select_native_effect_targets(
                    effect, caster, caster.position, actors, native_context=contexts
                )
            ],
            [1, 2],
        )
        fight = SimpleNamespace(
            actors={a.id: a for a in actors},
            walkable={(0, 0, 0), (1, -1, 4), (2, -2, 6)},
        )
        self.assertEqual(
            group_cells(fight, effect, caster.position, caster_id=1),
            ((0, 0, 0), (1, -1, 4), (2, -2, 6)),
        )

    def test_null_selector_uses_caster_origin_and_cast_cell_as_reference(self):
        effect = dict(
            area_class="anI", area_native="t-0-2", native_target_selector=None
        )
        caster = SimpleNamespace(
            id=1, team=0, position=(0, 0, 0), hp=10, physical_radius=0, direction=3
        )
        behind = SimpleNamespace(
            id=2, team=1, position=(-2, 0, 0), hp=10, physical_radius=0
        )
        ahead = SimpleNamespace(
            id=3, team=1, position=(2, 0, 0), hp=10, physical_radius=2
        )
        self.assertEqual(
            [
                a.id
                for a in select_native_effect_targets(
                    effect,
                    caster,
                    (2, 0, 0),
                    [caster, behind, ahead],
                    native_context={
                        a.id: {"is_eHH": False} for a in [caster, behind, ahead]
                    },
                )
            ],
            [1, 2],
        )

    def test_square_3x3_is_isotropic_and_directionless(self):
        effect = dict(area_class="anG", area_native="rectangle or square-3x3")
        self.assertEqual(
            area_offsets(effect),
            frozenset((x, y) for x in (-1, 0, 1) for y in (-1, 0, 1)),
        )
        with self.assertRaises(ValueError):
            oriented_area_offsets(
                dict(area_class="anI", area_native="t-0-2"),
                origin=(0, 0, 0),
                reference=(0, 0, 0),
            )
