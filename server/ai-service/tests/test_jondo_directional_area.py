"""Directional DTO/membership goldens against the existing pure World oracle."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_jondo_aoe_los as aoe_tests
from wakfu_ai.bridge.jondo_area import (
    area_projection,
    directional_geometry,
    directional_recipient,
)
from wakfu_ai.bridge.jondo_aoe_los import inverse_aoe_pairs
from wakfu_ai.bridge.jondo_snapshot import semantic_rows, summarize
from wakfu_ai.bridge.jondo_capabilities import project_support
from wakfu_server.combat_area_geometry import (
    native_area_contains,
    native_area_shape,
    oriented_area_offsets,
)
from wakfu_server.combat_effect_targets import (
    select_native_effect_targets,
    native_selector_policy,
    target_relation,
)


SHAPES = (
    dict(area_class="anz", area_native="Directed rectangle-3x3"),
    dict(area_class="anv", area_native="cone-3"),
    dict(area_class="anC", area_native="cone_inv-3"),
    dict(area_class="anI", area_native="t-1-2"),
    dict(area_class="anJ", area_native="t inv-barre:1-pied:2"),
    dict(area_class="anG", area_native="rectangle or square-3x1"),
    dict(area_class="anF", area_native="rectangular or square ring-w:1-2 / h:0-1"),
    dict(
        area_class="anE",
        area_native="ordered",
        native_area_points=[[2, 0], [0, 1], [2, 0]],
    ),
)


def effect(shape, selector=None, family=2):
    return dict(
        shape,
        effect_class=family,
        variant=0,
        minimum_level=0,
        maximum_level=100,
        application_flag="NONE",
        target_masks=[None] * 7,
        parameters=[10, 0],
        parameter_count=1,
        probability_base=100,
        probability_per_level=0,
        native_target_selector=selector,
        children=(),
    )


class DirectionalAreaTests(unittest.TestCase):
    def test_raw_dto_preserves_native_order_and_never_freezes_current_direction(self):
        for shape in SHAPES:
            for selector in (None, {"class": "fcE", "mask": 9}):
                with self.subTest(shape=shape, selector=selector):
                    native = effect(shape, selector)
                    projection = area_projection(native)
                    self.assertEqual(projection["fixedCells"], [])
                    dto = projection["nativeDirectionalArea"]
                    self.assertEqual(
                        dto,
                        dict(
                            version=1,
                            isotropic=False,
                            centerOnCaster=selector is None,
                            useTargetRadius=selector is not None,
                            rawOffsets=[
                                list(point) for point in native_area_shape(native)[0]
                            ],
                        ),
                    )
                    self.assertIsNotNone(directional_geometry(projection))
        square = area_projection(
            effect(dict(area_class="anG", area_native="rectangle or square-3x3"))
        )
        self.assertNotIn("nativeDirectionalArea", square)
        self.assertEqual(len(square["fixedCells"]), 9)

    def test_exact_membership_matches_world_for_rotations_facing_radius_and_null_selector(
        self,
    ):
        checked = 0
        for shape in SHAPES:
            for selector in (None, {"class": "fcE", "mask": 9}):
                native = effect(shape, selector)
                geometry = directional_geometry(area_projection(native))
                for origin, center, direction in (
                    *(((-4, 0, 0), (0, 0, 0), direction) for direction in (0, 3)),
                    ((4, 0, 0), (0, 0, 0), 1),
                    ((0, -4, 0), (0, 0, 0), 1),
                    ((0, 4, 0), (0, 0, 0), 1),
                    ((-1, -1, 0), (0, 0, 0), 1),
                    *((((0, 0, 0)), (0, 0, 0), direction) for direction in range(8)),
                ):
                    for radius in (0, 1, 2):
                        for x in range(-3, 4):
                            for y in range(-3, 4):
                                point = (x, y, 7)
                                expected = native_area_contains(
                                    native,
                                    origin=origin if selector is None else center,
                                    reference=center if selector is None else origin,
                                    point=point,
                                    direction=direction,
                                    radius=radius if selector is not None else 0,
                                )
                                actual = directional_recipient(
                                    geometry,
                                    center=center,
                                    origin=origin,
                                    point=point,
                                    radius=radius,
                                    direction=direction,
                                )
                                self.assertEqual(
                                    actual,
                                    expected,
                                    (
                                        shape,
                                        origin,
                                        center,
                                        direction,
                                        radius,
                                        point,
                                        selector,
                                    ),
                                )
                                checked += 1
        self.assertEqual(checked, len(SHAPES) * 2 * 14 * 3 * 49)

    def test_diagonal_selfcast_membership_is_not_forward_cell_enumeration(self):
        native = effect(
            dict(area_class="anE", area_native="ordered", native_area_points=[[2, 0]])
        )
        geometry = directional_geometry(area_projection(native))
        self.assertEqual(
            oriented_area_offsets(
                native, origin=(0, 0, 0), reference=(0, 0, 0), direction=2
            ),
            ((2, 2),),
        )
        self.assertTrue(
            directional_recipient(
                geometry,
                center=(0, 0, 0),
                origin=(0, 0, 0),
                point=(1, 1, 0),
                radius=0,
                direction=2,
            )
        )
        self.assertFalse(
            directional_recipient(
                geometry,
                center=(0, 0, 0),
                origin=(0, 0, 0),
                point=(2, 2, 0),
                radius=0,
                direction=2,
            )
        )

    def test_complete_native_selector_oracle_null_fcE_anchor_and_all_relations(self):
        caster = SimpleNamespace(
            id=1, team=0, hp=100, position=(0, 0, 0), physical_radius=0, direction=2
        )
        actors = [
            caster,
            SimpleNamespace(
                id=2, team=0, hp=100, position=(1, 1, 0), physical_radius=1
            ),
            SimpleNamespace(
                id=3, team=1, hp=100, position=(5, 0, 0), physical_radius=1
            ),
            SimpleNamespace(
                id=4, team=1, hp=100, position=(0, -1, 0), physical_radius=0
            ),
        ]
        contexts = {
            actor.id: dict(
                is_amO=True,
                bEe=True,
                is_Qq=False,
                is_eGj=True,
                UNTARGETTABLE_BY_OTHER=False,
                is_eHH=True,
                buX=False,
            )
            for actor in actors
        }
        shapes = (
            *SHAPES,
            dict(area_class="anD", area_native="point"),
            dict(area_class="anu", area_native="circle-2"),
            dict(area_class="anw", area_native="cross-h2b2-g1d1"),
        )
        checked = 0
        for shape in shapes:
            for selector in (
                None,
                *({"class": "fcE", "mask": mask} for mask in (1, 3, 5, 9)),
            ):
                native = effect(shape, selector)
                projection = area_projection(native)
                geometry = directional_geometry(projection)
                self.assertIs(projection["nativeAreaCenterOnCaster"], selector is None)
                self.assertIs(
                    projection["nativeAreaUseTargetRadius"], selector is not None
                )
                for aim in ((0, 0, 0), (5, 0, 0), (-2, 0, 0), (0, 3, 0), (1, 1, 0)):
                    expected = {
                        actor.id
                        for actor in select_native_effect_targets(
                            native, caster, aim, actors, native_context=contexts
                        )
                    }
                    predicted = set()
                    for actor in actors:
                        if (
                            target_relation(caster, actor)
                            not in native_selector_policy(native)["relations"]
                        ):
                            continue
                        if geometry is not None:
                            inside = directional_recipient(
                                geometry,
                                origin=caster.position,
                                center=aim,
                                point=actor.position,
                                radius=actor.physical_radius,
                                direction=caster.direction,
                            )
                        else:
                            anchor = (
                                caster.position
                                if projection["nativeAreaCenterOnCaster"]
                                else aim
                            )
                            radius = (
                                actor.physical_radius
                                if projection["nativeAreaUseTargetRadius"]
                                else 0
                            )
                            x, y = (
                                actor.position[0] - anchor[0],
                                actor.position[1] - anchor[1],
                            )
                            inside = any(
                                abs(x - px) <= radius and abs(y - py) <= radius
                                for px, py in projection["fixedCells"]
                            )
                        if inside:
                            predicted.add(actor.id)
                    self.assertEqual(predicted, expected, (shape, selector, aim))
                    checked += 1
        self.assertEqual(checked, 275)
        null_point = effect(dict(area_class="anD", area_native="point"))
        self.assertEqual(
            {
                actor.id
                for actor in select_native_effect_targets(
                    null_point, caster, (5, 0, 0), actors, native_context=contexts
                )
            },
            {caster.id},
        )

    def test_unknown_modes_shapes_and_missing_selector_fail_closed(self):
        projection = area_projection(effect(SHAPES[0]))
        for field, value in (
            ("version", 2),
            ("version", True),
            ("useTargetRadius", None),
            ("rawOffsets", [[True, 0]]),
            ("isotropic", True),
        ):
            altered = deepcopy(projection)
            altered["nativeDirectionalArea"][field] = value
            self.assertIsNone(directional_geometry(altered))
        with self.assertRaises(ValueError):
            area_projection(SHAPES[0])
        with self.assertRaises(ValueError):
            area_projection(
                effect(dict(area_class="unknown", area_native="guess-circle"))
            )

    def test_semantic_and_support_exports_use_the_same_native_descriptor(self):
        # Only unrelated catalog/arithmetic imports are fixtures. Geometry and
        # production semantic/support projection execute their actual paths.
        modules = {
            "wakfu_server.combat_damage_parameters": SimpleNamespace(
                damage_parameter_specification=lambda *args: dict(
                    base_kind=0, base=10, coefficient_mask=0
                )
            ),
            "wakfu_server.combat_effect_resolver": SimpleNamespace(
                variant_accepts=lambda *args: True
            ),
            "wakfu_server.combat_summon": SimpleNamespace(
                summon_specification=lambda *args, **kwargs: None
            ),
            "wakfu_server.monsters": SimpleNamespace(reference=lambda *args: None),
        }
        actor = SimpleNamespace(
            id=1, team=0, effective_level=1, direction=2, position=(0, 0, 0)
        )
        fight = SimpleNamespace(actors={1: actor})
        with patch.dict("sys.modules", modules), patch(
            "wakfu_server.combat_static_catalogs.characteristic_registry",
            return_value={
                "effects": {
                    "48": dict(
                        operation="gain_current", fixed_stat_id=2, fixed_stat_name="AP"
                    )
                }
            },
        ):
            for shape in SHAPES:
                native = effect(shape, {"class": "fcE", "mask": 9})
                rows, unknown = semantic_rows(
                    SimpleNamespace(effects={"1": native}), [1], 1
                )
                self.assertFalse(unknown)
                self.assertTrue(rows)
                self.assertTrue(all(row["fixedCells"] == [] for row in rows))
                self.assertTrue(
                    all(
                        row["nativeDirectionalArea"]
                        == area_projection(native)["nativeDirectionalArea"]
                        for row in rows
                    )
                )
                buff = effect(shape, {"class": "fcE", "mask": 5}, family=48)
                support = project_support(
                    SimpleNamespace(effects={"1": buff}),
                    [1],
                    1,
                    fight=fight,
                    actor=actor,
                    actors=[dict(id=1, hp=20, team=0)],
                )
                self.assertTrue(support["effects"])
                self.assertEqual(
                    support["effects"][0]["nativeDirectionalArea"],
                    area_projection(buff)["nativeDirectionalArea"],
                )
            native = effect(dict(area_class="unknown", area_native="unknown"))
            rows, unknown = semantic_rows(
                SimpleNamespace(effects={"1": native}), [1], 1
            )
            self.assertEqual(rows, [])
            self.assertTrue(unknown)
            self.assertEqual(summarize(rows, unknown)["damage"], 0)

    def test_directional_new_centers_have_actual_clear_blocked_and_missing_snapshot_evidence(
        self,
    ):
        producer = aoe_tests.InverseAoeLosTests()
        for selector, center in (
            ({"class": "fcE", "mask": 9}, (2, 0, 0)),
            (None, (-2, 0, 0)),
        ):
            native = effect(
                dict(area_class="anz", area_native="Directed rectangle-1x4"), selector
            )
            row = dict(
                aoe_tests.row_for(aoe_tests.SHAPES[0]), **area_projection(native)
            )
            for blocked in (False, True):
                _, _, visible, _ = producer.snapshot(
                    aoe_tests.SHAPES[0],
                    blocked=blocked,
                    projected_row=row,
                    aim_center=center,
                )
                self.assertIs(visible, not blocked, (selector, center))
            _, _, visible, _ = producer.snapshot(
                aoe_tests.SHAPES[0], missing=True, projected_row=row, aim_center=center
            )
            self.assertIsNone(visible)

    def test_inverse_centers_cover_four_cardinal_aims_and_actual_origin_membership(
        self,
    ):
        cells = tuple((x, y, 0) for x in range(-2, 9) for y in range(-4, 5))
        indices = {cell: index for index, cell in enumerate(cells)}
        native = effect(
            dict(area_class="anE", area_native="ordered", native_area_points=[[1, 0]]),
            {"class": "fcE", "mask": 9},
        )
        row = dict(target="enemy", nativeInArea=True, **area_projection(native))
        spell = dict(rows=[row], needsLineOfSight=True, minRange=0, maxRange=8)
        enemy = dict(id=2, hp=20, team=1, cell=indices[3, 0, 0], physicalRadius=0)
        for origin, wanted in (
            ((0, 0, 0), (2, 0, 0)),
            ((6, 0, 0), (4, 0, 0)),
            ((3, -3, 0), (3, -1, 0)),
            ((3, 3, 0), (3, 1, 0)),
        ):
            caster = dict(id=1, hp=20, team=0, cell=indices[origin], direction=2)
            with patch("wakfu_ai.bridge.jondo_aoe_los.clock_now", return_value=0):
                pairs = inverse_aoe_pairs(
                    [spell],
                    [caster, enemy],
                    cells,
                    indices,
                    [origin],
                    {origin, (3, 0, 0)},
                    actor_id=1,
                    deadline=1,
                )
            self.assertIn((origin, wanted), pairs)
            self.assertLessEqual(len(pairs), 64)
            for start, center in pairs:
                self.assertTrue(
                    native_area_contains(
                        native,
                        origin=center,
                        reference=start,
                        point=(3, 0, 0),
                        direction=2,
                        radius=0,
                    )
                )

    def test_null_directional_steering_aims_anchor_on_each_origin_with_legal_minimum_range(
        self,
    ):
        cells = tuple((x, y, 0) for x in range(-5, 7) for y in range(-5, 6))
        indices = {cell: index for index, cell in enumerate(cells)}
        native = effect(dict(area_class="anz", area_native="Directed rectangle-1x3"))
        row = dict(target="enemy", nativeInArea=True, **area_projection(native))
        book = dict(rows=[row], needsLineOfSight=True, minRange=2, maxRange=3)
        caster = dict(id=1, hp=100, team=0, cell=indices[0, 0, 0], direction=2)
        enemy = dict(id=2, hp=100, team=1, cell=indices[2, 0, 0], physicalRadius=1)
        for origin in ((0, 0, 0), (1, 0, 0)):
            caster["cell"] = indices[origin]
            with patch("wakfu_ai.bridge.jondo_aoe_los.clock_now", return_value=0):
                pairs = inverse_aoe_pairs(
                    [book],
                    [caster, enemy],
                    cells,
                    indices,
                    [origin],
                    {origin, (2, 0, 0)},
                    actor_id=1,
                    deadline=1,
                )
            self.assertTrue(pairs)
            for start, aim in pairs:
                self.assertTrue(
                    2 <= abs(start[0] - aim[0]) + abs(start[1] - aim[1]) <= 3
                )
                self.assertTrue(
                    native_area_contains(
                        native,
                        origin=start,
                        reference=aim,
                        point=(2, 0, 0),
                        direction=2,
                        radius=0,
                    )
                )
            self.assertIn((origin, (origin[0] - 2, 0, 0)), pairs)


if __name__ == "__main__":
    unittest.main()
