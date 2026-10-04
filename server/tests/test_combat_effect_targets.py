import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_targets import (
    area_offsets,
    select_effect_targets,
    UnsupportedEffectArea,
)


def effect(kind, description):
    return dict(area_class=kind, area_native=description)


class EffectTargetTests(unittest.TestCase):
    def test_native_cross_ring_excludes_inner_cells_and_sorts_radii(self):
        expected = frozenset(
            (x, y) for n in (1, 2, 3) for x, y in ((0, -n), (0, n), (n, 0), (-n, 0))
        )
        self.assertEqual(area_offsets(effect("any", "crossRing-1-3")), expected)
        self.assertEqual(area_offsets(effect("any", "crossRing-3-1")), expected)
        self.assertEqual(area_offsets(effect("any", "crossRing-0-0")), {(0, 0)})

    def test_native_circle_ring_and_cross_offsets(self):
        circle = area_offsets(effect("anu", "circle-2"))
        self.assertEqual(len(circle), 13)
        self.assertIn((1, 1), circle)
        self.assertNotIn((2, 1), circle)
        self.assertEqual(area_offsets(effect("anH", "ring-1-2")), circle - {(0, 0)})
        self.assertEqual(
            area_offsets(effect("anw", "cross-h2b2-g2d2")),
            frozenset(
                {
                    (0, 0),
                    (0, -1),
                    (0, -2),
                    (0, 1),
                    (0, 2),
                    (1, 0),
                    (2, 0),
                    (-1, 0),
                    (-2, 0),
                }
            ),
        )

    def test_relations_empty_center_and_native_xy_height(self):
        actors = [
            SimpleNamespace(id=i, team=team, position=pos, hp=hp)
            for i, team, pos, hp in [
                (1, 0, (0, 0, 0), 10),
                (2, 0, (1, 0, 9), 10),
                (3, 1, (-1, 0, 0), 10),
                (4, 1, (0, 1, 0), 0),
            ]
        ]
        circle = effect("anu", "circle-1")
        for relation, identity in [("self", 1), ("ally", 2), ("enemy", 3)]:
            self.assertEqual(
                [
                    a.id
                    for a in select_effect_targets(
                        circle, actors[0], (0, 0, 0), actors, relations={relation}
                    )
                ],
                [identity],
            )
        self.assertEqual(
            select_effect_targets(
                effect("anD", "point"),
                actors[0],
                (2, 0, 0),
                actors,
                relations={"enemy", "ally", "self"},
            ),
            (),
        )
        self.assertEqual(
            [
                a.id
                for a in select_effect_targets(
                    circle, actors[0], (2, 0, 0), actors, relations={"ally"}
                )
            ],
            [2],
        )

    def test_unknown_and_asymmetric_areas_fail_closed(self):
        for area in [
            effect("anE", "forme à base de points"),
            effect("anw", "cross-h1b2-g1d1"),
        ]:
            with self.assertRaises(UnsupportedEffectArea):
                area_offsets(area)
        self.assertEqual(area_offsets(effect("anA", "empty")), frozenset())

    def test_event_masks_do_not_implicitly_select_targets(self):
        area = dict(
            effect("anD", "point"),
            target_masks=[None, None, [1028], None, None, None, None],
        )
        self.assertEqual(area_offsets(area), frozenset({(0, 0)}))


class NativeSelectorTests(unittest.TestCase):
    def test_null_selector_area_is_anchored_to_caster(self):
        from wakfu_server.combat_effect_targets import select_native_effect_targets

        caster = SimpleNamespace(id=1, team=0, position=(0, 0, 0), hp=10)
        remote = SimpleNamespace(id=2, team=1, position=(10, 0, 0), hp=10)
        data = dict(effect("anD", "point"), native_target_selector=None)
        contexts = {1: {"is_eHH": False}, 2: {"is_eHH": False}}
        self.assertEqual(
            select_native_effect_targets(
                data, caster, remote.position, [caster, remote], native_context=contexts
            ),
            (caster,),
        )
        caster.position = remote.position
        self.assertEqual(
            select_native_effect_targets(
                data, caster, (0, 0, 0), [caster, remote], native_context=contexts
            ),
            (caster, remote),
        )

    def test_native_proven_relation_table(self):
        from wakfu_server.combat_effect_targets import native_selector_policy

        expected = {
            0: {"self", "ally", "enemy"},
            1: {"self", "ally", "enemy"},
            2: {"self"},
            3: {"self"},
            4: {"self", "ally"},
            5: {"self", "ally"},
            8: {"enemy"},
            9: {"enemy"},
            256: {"ally", "enemy"},
            257: {"ally", "enemy"},
            261: {"ally"},
        }
        for mask, relations in expected.items():
            policy = native_selector_policy(
                {"native_target_selector": {"class": "fcE", "mask": mask}}
            )
            self.assertEqual(policy["relations"], relations)
            self.assertEqual(policy["in_area"], bool(mask & 1))

    def test_self_empty_area_is_global_without_area_flag(self):
        from wakfu_server.combat_effect_targets import select_native_effect_targets

        caster = SimpleNamespace(id=1, team=0, position=(0, 0, 0), hp=10)
        data = dict(
            effect("anA", "empty"), native_target_selector={"class": "fcE", "mask": 2}
        )
        self.assertEqual(
            select_native_effect_targets(
                data,
                caster,
                (10, 10, 0),
                [caster],
                native_context={1: {"bEe": True, "is_Qq": False}},
            ),
            (caster,),
        )
        data["native_target_selector"]["mask"] = 3
        self.assertEqual(
            select_native_effect_targets(
                data,
                caster,
                (10, 10, 0),
                [caster],
                native_context={1: {"bEe": True, "is_Qq": False}},
            ),
            (),
        )

    def test_missing_unknown_and_null_are_distinct(self):
        from wakfu_server.combat_effect_targets import (
            native_selector_policy,
            UnsupportedTargetSelector,
        )

        for data in [
            {},
            {"native_target_selector": {"class": "fcE", "mask": 1028}},
            {"native_target_selector": {"class": "other", "mask": 1}},
        ]:
            with self.assertRaises(UnsupportedTargetSelector):
                native_selector_policy(data)
        self.assertTrue(
            native_selector_policy({"native_target_selector": None})["in_area"]
        )


class NativeTargetContextTests(unittest.TestCase):
    def setUp(self):
        self.caster = SimpleNamespace(id=1, team=0, position=(0, 0, 0), hp=10)
        self.target = SimpleNamespace(id=2, team=1, position=(1, 0, 0), hp=10)
        self.context = {
            i: {
                "bEe": True,
                "is_amO": True,
                "is_eGj": True,
                "is_Qq": False,
                "is_eHH": True,
                "bcN": 0,
                "UNTARGETTABLE_BY_OTHER": False,
                "buX": False,
            }
            for i in (1, 2)
        }

    def select(self, mask):
        from wakfu_server.combat_effect_targets import select_native_effect_targets

        data = dict(
            effect("anu", "circle-1"),
            native_target_selector={"class": "fcE", "mask": mask},
        )
        return select_native_effect_targets(
            data, self.caster, (0, 0, 0), [self.target], native_context=self.context
        )

    def test_native_target_properties_and_bypass(self):
        self.assertEqual(self.select(9 | (1 << 50)), (self.target,))
        self.context[2]["bcN"] = -1
        self.assertEqual(self.select(9 | (1 << 50)), ())
        self.context[2]["bcN"] = 0
        self.context[2]["UNTARGETTABLE_BY_OTHER"] = True
        self.assertEqual(self.select(9), ())
        self.assertEqual(self.select(8), (self.target,))
        self.context[2]["UNTARGETTABLE_BY_OTHER"] = False
        self.context[2]["buX"] = True
        self.assertEqual(self.select(9), ())
        self.assertEqual(self.select(9 | 8192), (self.target,))
        self.context[2]["bEe"] = False
        self.assertEqual(self.select(9 | 8192), ())

    def test_subtargets_need_explicit_native_eligibility(self):
        self.context[2].update(is_eGj=False, is_Qq=True, bcR=False)
        self.assertEqual(self.select(1), ())
        self.assertEqual(self.select(1 | (1 << 51)), (self.target,))
        self.assertEqual(self.select(1 | (1 << 51) | (1 << 49)), ())
        self.assertEqual(self.select(1 | (1 << 47)), ())

    def test_missing_context_fails_closed(self):
        from wakfu_server.combat_effect_targets import UnsupportedTargetSelector

        del self.context[2]["UNTARGETTABLE_BY_OTHER"]
        with self.assertRaises(UnsupportedTargetSelector):
            self.select(9)

    def test_native_summon_and_subtarget_requirements(self):
        self.assertEqual(self.select(65 | (1 << 51)), ())
        self.context[2].update(dTE=False)
        self.assertEqual(self.select(4097), ())
        self.context[2].update(dTE=True, dpu_id=1, baG=False, baK=False)
        self.assertEqual(self.select(4097), (self.target,))
        self.context[2]["dpu_id"] = 99
        self.assertEqual(self.select(4097), ())
        self.context[2].update(dpu_id=1, baG=True)
        self.assertEqual(self.select(4097), ())
