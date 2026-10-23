"""Native positive-eGj filters do not independently authorize fanout."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

import test_combat_effect_resolver as fixture


class GlobalTypedFighterSelectionTests(unittest.TestCase):
    setUp = fixture.NativeResolverTests.setUp

    def test_unadmitted_positive_fighter_filters_preserve_chosen_recipient(self):
        boss = SimpleNamespace(
            id=-200, team=1, position=(5, 5, 0), hp=10, physical_radius=0
        )
        self.actors.append(boss)
        self.native[-200] = dict(self.native[1])
        self.effect.update(
            effect_class=304,
            area_class="anD",
            area_native="point",
            parameter_count=3,
            parameters=[9028, 0, 1, 0, -1, 0],
        )
        mask = 16 | (1 << 47)
        self.effect["native_target_selector"] = dict(class_="fcE", mask=mask)
        self.effect["native_target_selector"]["class"] = "fcE"
        self.resolver.direct_target_policies = {"50": [304, False, False]}
        invocation = replace(
            self.invocation,
            caster_id=-200,
            target_id=-200,
            cell=boss.position,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )
        # Native16/47 are eligibility filters, not permission for fresh
        # population expansion without an admitted encounter policy.
        for global_mask in (16, mask):
            with self.subTest(
                contract="unadmitted positive eGj filter", mask=global_mask
            ):
                self.effect["native_target_selector"]["mask"] = global_mask
                self.assertEqual(
                    [row.target_id for row in self.resolver(self.effect, invocation)],
                    [-200],
                )
        self.effect["native_target_selector"]["mask"] = mask
        with self.subTest(contract="actual chosen PV"):
            self.assertEqual(
                [
                    row.target_id
                    for row in self.resolver(
                        self.effect, replace(invocation, native_preselected_target=True)
                    )
                ],
                [-200],
            )
        with self.subTest(contract="retained replay"):
            self.assertEqual(
                [
                    row.target_id
                    for row in self.resolver(
                        self.effect,
                        replace(invocation, wakemu_fresh_child_selection=False),
                    )
                ],
                [-200],
            )
        with self.subTest(contract="actual triggering Qe"):
            self.assertEqual(
                [
                    row.target_id
                    for row in self.resolver(
                        self.effect,
                        replace(
                            invocation,
                            native_trigger_context={"caster_id": 1, "target_id": -200},
                        ),
                    )
                ],
                [-200],
            )
        with self.subTest(contract="type47 alone preserves chosen PV"):
            self.effect["native_target_selector"]["mask"] = 1 << 47
            self.assertEqual(
                [row.target_id for row in self.resolver(self.effect, invocation)],
                [-200],
            )
        with self.subTest(contract="point AREA recipient"):
            self.effect["native_target_selector"]["mask"] = 16 | 1
            self.assertEqual(
                [
                    row.target_id
                    for row in self.resolver(
                        self.effect,
                        replace(invocation, target_id=1, cell=self.actors[0].position),
                    )
                ],
                [1],
            )
        with self.subTest(contract="event-bound group"):
            self.effect.update(effect_class=330, parameter_count=0, parameters=[])
            self.effect["native_target_selector"]["mask"] = mask
            self.resolver.direct_target_policies = {"50": [330, False, False]}
            self.assertEqual(
                [
                    row.target_id
                    for row in self.resolver(
                        self.effect,
                        replace(
                            invocation,
                            native_trigger_context={"caster_id": 1, "target_id": -200},
                        ),
                    )
                ],
                [-200],
            )
        with self.subTest(contract="swap-owning group"):
            self.effect.update(
                effect_class=330,
                parameter_count=6,
                parameters=[0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0],
            )
            self.effect["native_target_selector"]["mask"] = mask
            self.resolver.direct_target_policies = {"50": [330, False, False]}
            self.assertEqual(
                [row.target_id for row in self.resolver(self.effect, invocation)],
                [-200],
            )
