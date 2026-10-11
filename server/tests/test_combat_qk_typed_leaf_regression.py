"""Typed fresh-PV selectors retain recipient discovery after group rebinding."""
import unittest
from dataclasses import replace
from test_combat_fresh_qk_selection_qualified import FreshQKSelectionTests


class TypedQKLeafTests(unittest.TestCase):
    def test_typed_qk_point_leaf_reselects_indexed_fighter_after_rebind(self):
        f, invocation = FreshQKSelectionTests().fixture()
        f.effect.update(
            effect_class=422,
            native_target_selector={"class": "fcE", "mask": (1 << 47) | (1 << 50)},
        )
        f.resolver.direct_target_policies = {"50": [422, False, False]}
        # No AREA bit: native fcE.a accepts both typed, indexed fighters,
        # including the caster outside the invocation's point geometry.
        self.assertEqual(
            [i.target_id for i in f.resolver(f.effect, invocation)], [1, 2]
        )
        self.assertEqual(
            [
                i.target_id
                for i in f.resolver(
                    f.effect, replace(invocation, wakemu_fresh_child_selection=False)
                )
            ],
            [3],
        )
        f.native[2]["bcN"] = -1
        self.assertEqual([i.target_id for i in f.resolver(f.effect, invocation)], [1])
        f.native[1]["bcN"] = -1
        self.assertEqual(f.resolver(f.effect, invocation), ())

    def test_area_qk_leaf_without_explicit_pv_keeps_geometry_selection(self):
        f, invocation = FreshQKSelectionTests().fixture()
        f.effect.update(effect_class=3)
        f.resolver.direct_target_policies = {"50": [3, False, False]}
        selected = f.resolver(
            f.effect, replace(invocation, native_explicit_target=False)
        )
        self.assertEqual([i.target_id for i in selected], [2])

    def test_nonpoint_area_qk_leaf_keeps_geometry_selection(self):
        f, invocation = FreshQKSelectionTests().fixture()
        f.effect.update(effect_class=3, area_class="anu", area_native="circle-1")
        f.resolver.direct_target_policies = {"50": [3, False, False]}
        self.assertEqual(
            [i.target_id for i in f.resolver(f.effect, invocation)], [1, 2]
        )

    def test_original_preselected_target_bypasses_fresh_selection(self):
        f, invocation = FreshQKSelectionTests().fixture()
        f.effect.update(
            effect_class=422,
            native_target_selector={"class": "fcE", "mask": (1 << 47) | (1 << 50)},
        )
        f.resolver.direct_target_policies = {"50": [422, False, False]}
        self.assertEqual(
            [
                i.target_id
                for i in f.resolver(
                    f.effect, replace(invocation, native_preselected_target=True)
                )
            ],
            [3],
        )
