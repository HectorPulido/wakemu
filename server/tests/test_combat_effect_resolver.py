import unittest
from types import SimpleNamespace
from dataclasses import replace
from wakfu_server.combat_effect_dispatch import EffectInvocation, EffectDispatcher
from wakfu_server.combat_effect_resolver import (
    NativeEffectResolver,
    EffectResolutionContext,
    TriggerEligibility,
    UnknownEffectResolution,
)
from wakfu_server.combat_effect_targets import UnsupportedTargetSelector


class NativeResolverTests(unittest.TestCase):
    def test_preselection_is_consumed_before_runner_creates_area_children(self):
        definition = dict(
            self.effect,
            minimum_level=0,
            maximum_level=100,
            parameters=[],
            parameter_count=0,
            probability_base=100,
            probability_per_level=0,
            criteria="",
            effect_class=400,
        )
        descendants = []

        def apply(effect, values, invocation):
            self.assertFalse(invocation.native_preselected_target)
            descendants.extend(self.resolver(effect, invocation))
            return True

        dispatcher = EffectDispatcher(
            {"50": definition},
            {400: apply},
            resolve=self.resolver,
            condition_context=lambda i: {},
            probability_accepts=lambda p, i: True,
            group_cells=lambda e, i: (),
            actor_position=lambda i: self.actors[0].position,
        )
        self.assertTrue(
            dispatcher.execute(
                replace(
                    self.invocation,
                    target_id=2,
                    native_preselected_target=True,
                )
            )
        )
        self.assertEqual([i.target_id for i in descendants], [1, 2, 3])

    def test_preselected_state_recipient_bypasses_empty_area_and_aZX(self):
        self.effect.update(area_class="anA", area_native="empty")
        self.resolver.direct_target_policies = {50: [400, True, False]}
        self.effect["effect_class"] = 400
        invocation = replace(
            self.invocation, target_id=2, native_preselected_target=True
        )
        self.assertEqual(
            [i.target_id for i in self.resolver(self.effect, invocation)], [2]
        )
        self.assertEqual(
            self.resolver(
                self.effect, replace(invocation, native_preselected_target=False)
            ),
            (),
        )

    def test_preselected_recipient_is_not_reselected_as_caster_or_area(self):
        self.effect["native_target_selector"]["mask"] = 2
        invocation = replace(
            self.invocation, target_id=2, native_preselected_target=True
        )
        self.assertEqual(
            [i.target_id for i in self.resolver(self.effect, invocation)], [2]
        )
        self.assertEqual(
            self.resolver(self.effect, replace(invocation, target_id=99)), ()
        )

    def test_fresh_zero_mask_enumerates_candidates_but_replay_keeps_explicit_pv(self):
        self.effect.update(
            effect_class=330, parameter_count=0, area_class="anD", area_native="point"
        )
        self.effect["native_target_selector"] = {"class": "fcE", "mask": 0}
        self.resolver.direct_target_policies = {"50": [330, False, False]}
        self.actors[1].hp = 0
        invocation = replace(self.invocation, target_id=3, native_explicit_target=True)
        self.assertEqual(
            [row.target_id for row in self.resolver(self.effect, invocation)], [3]
        )
        selected = self.resolver(
            self.effect, replace(invocation, wakemu_fresh_child_selection=True)
        )
        self.assertEqual([row.target_id for row in selected], [1, 2, 3])

    def test_zero_mask_event_group_preserves_its_trigger_recipient(self):
        self.effect.update(
            effect_class=330,
            parameter_count=0,
            area_class="anD",
            area_native="point",
        )
        self.effect["native_target_selector"] = {"class": "fcE", "mask": 0}
        self.resolver.direct_target_policies = {"50": [330, False, False]}
        invocation = replace(
            self.invocation,
            target_id=3,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
            native_trigger_context={"target_id": 3},
        )
        self.assertEqual(
            [row.target_id for row in self.resolver(self.effect, invocation)], [3]
        )

    def test_fresh_zero_mask_leaf_keeps_the_transmitted_hit_recipient(self):
        self.effect.update(effect_class=5, area_class="anD", area_native="point")
        self.effect["native_target_selector"] = {"class": "fcE", "mask": 0}
        self.resolver.direct_target_policies = {"50": [5, False, False]}
        invocation = replace(
            self.invocation,
            target_id=3,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )
        self.assertEqual(
            [row.target_id for row in self.resolver(self.effect, invocation)], [3]
        )

    def test_removal_only_mask_does_not_defer_initial_application(self):
        self.effect["target_masks"][2] = [6, 7, 8]
        selected = self.resolver(self.effect, self.invocation)
        self.assertEqual([inv.target_id for inv in selected], [1, 2, 3])

    def test_transmitted_rebound_point_recipient_keeps_identity(self):
        self.effect.update(effect_class=25, area_class="anD", area_native="point")
        self.effect["native_target_selector"] = {"class": "fcE", "mask": 129}
        self.resolver.direct_target_policies = {"50": [25, False, False]}
        invocation = replace(
            self.invocation,
            caster_id=2,
            target_id=2,
            cell=self.actors[1].position,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )
        self.assertEqual(
            [row.target_id for row in self.resolver(self.effect, invocation)], [2]
        )
        # Without the transmitted PV, normal ally selection excludes self.
        self.assertEqual(
            self.resolver(
                self.effect, replace(invocation, native_explicit_target=False)
            ),
            (),
        )
        # A non-point area still selects its allies instead of collapsing to
        # the rebound caster's identity.
        self.effect.update(area_class="anu", area_native="circle-2")
        self.assertEqual(
            [row.target_id for row in self.resolver(self.effect, invocation)], [1]
        )

    def setUp(self):
        self.actors = [
            SimpleNamespace(id=i, team=t, position=p, hp=10, physical_radius=0)
            for i, t, p in [(1, 0, (0, 0, 0)), (2, 0, (1, 0, 9)), (3, 1, (-1, 0, 0))]
        ]
        self.native = {
            i: dict(
                bEe=True,
                is_amO=True,
                is_eGj=True,
                is_Qq=False,
                is_eHH=True,
                UNTARGETTABLE_BY_OTHER=False,
                buX=False,
            )
            for i in (1, 2, 3)
        }
        self.context = EffectResolutionContext(
            "EFFECTS_ONLY", "immediate", "actors", True
        )
        self.resolver = NativeEffectResolver(
            actors=lambda e, i: self.actors,
            native_context=lambda e, i: self.native,
            context=lambda e, i: self.context,
        )
        self.effect = dict(
            variant=0,
            target_masks=[None] * 7,
            area_class="anu",
            area_native="circle-1",
            native_target_selector=dict(class_="fcE", mask=1),
        )
        self.effect["native_target_selector"]["class"] = "fcE"
        self.invocation = EffectInvocation(50, 20, 1, None, (0, 0, 0))

    def test_area_relations_variant_and_identity(self):
        selected = self.resolver(self.effect, self.invocation)
        self.assertEqual([i.target_id for i in selected], [1, 2, 3])
        self.assertTrue(
            all(
                i.reference == 50 and i.level == 20 and i.cell == (0, 0, 0)
                for i in selected
            )
        )
        self.effect["native_target_selector"]["mask"] = 9
        self.assertEqual(
            [i.target_id for i in self.resolver(self.effect, self.invocation)], [3]
        )
        self.effect["variant"] = 1
        self.assertEqual(self.resolver(self.effect, self.invocation), ())
        self.context = replace(self.context, variant_mode="CRITICALS_ONLY")
        self.assertEqual(
            [i.target_id for i in self.resolver(self.effect, self.invocation)], [3]
        )
        self.context = replace(self.context, variant_mode="ALL")
        self.effect["variant"] = 0
        self.assertEqual(len(self.resolver(self.effect, self.invocation)), 1)

    def test_self_bypasses_empty_area_and_cells_do_not_fabricate_actor(self):
        self.effect.update(area_class="anA", area_native="empty")
        self.effect["native_target_selector"]["mask"] = 2
        self.assertEqual(
            [i.target_id for i in self.resolver(self.effect, self.invocation)], [1]
        )
        self.effect.update(area_class="anD", area_native="point")
        self.effect["native_target_selector"]["mask"] = 1
        empty = replace(self.invocation, cell=(8, 8, 0))
        self.assertEqual(self.resolver(self.effect, empty), ())
        self.context = replace(self.context, selection="cell")
        with self.assertRaises(UnknownEffectResolution):
            self.resolver(self.effect, empty)
        self.resolver.cell_eligible = lambda e, i: True
        selected = self.resolver(self.effect, empty)
        self.assertEqual(selected, (replace(empty, native_target_cell_argument=True),))
        self.assertIsNone(selected[0].target_id)

    def test_actor_child_does_not_inherit_parent_cell_criterion_argument(self):
        invocation = replace(self.invocation, native_target_cell_argument=True)
        selected = self.resolver(self.effect, invocation)
        self.assertEqual([row.target_id for row in selected], [1, 2, 3])
        self.assertTrue(all(not row.native_target_cell_argument for row in selected))

    def test_events_require_verified_apply_channel_and_remove_has_separate_path(self):
        self.effect["target_masks"][0] = [1028]
        with self.assertRaises(UnknownEffectResolution):
            self.resolver(self.effect, self.invocation)
        trigger = TriggerEligibility((1028,), 1, "standard", False)
        self.context = replace(self.context, delivery="event", trigger=trigger)
        with self.assertRaises(UnknownEffectResolution):
            self.resolver(self.effect, self.invocation)
        self.context = replace(
            self.context, trigger=replace(trigger, guards_verified=True)
        )
        self.assertEqual(len(self.resolver(self.effect, self.invocation)), 3)
        self.context = replace(
            self.context,
            trigger=replace(trigger, guards_verified=True, event_bits=(99,)),
        )
        self.assertEqual(self.resolver(self.effect, self.invocation), ())
        self.effect["target_masks"][2] = [1028]
        self.context = replace(
            self.context, trigger=replace(trigger, guards_verified=True, channel=4)
        )
        with self.assertRaises(UnknownEffectResolution):
            self.resolver(self.effect, self.invocation)

    def test_missing_context_unknown_variant_and_emitted_mask(self):
        self.effect["target_masks"][6] = [1028]
        self.assertEqual(len(self.resolver(self.effect, self.invocation)), 3)
        del self.native[2]["bEe"]
        with self.assertRaises(UnsupportedTargetSelector):
            self.resolver(self.effect, self.invocation)
        self.effect["variant"] = 2
        with self.assertRaises(UnknownEffectResolution):
            self.resolver(self.effect, self.invocation)

    def test_dispatcher_reads_live_actor_properties_after_previous_effect(self):
        definitions = {
            str(ref): dict(
                self.effect,
                minimum_level=0,
                maximum_level=100,
                parameters=[10, 0],
                parameter_count=1,
                probability_base=100,
                probability_per_level=0,
                criteria="",
                effect_class=1,
            )
            for ref in (50, 51)
        }
        calls = []

        def apply(effect, values, invocation):
            calls.append((invocation.reference, invocation.target_id))
            if invocation.reference == 50:
                self.native[2]["bEe"] = False
            return True

        dispatcher = EffectDispatcher(
            definitions,
            {1: apply},
            resolve=self.resolver,
            condition_context=lambda i: {},
            probability_accepts=lambda p, i: True,
            group_cells=lambda e, i: (),
            actor_position=lambda i: self.actors[0].position,
        )
        dispatcher.execute(self.invocation)
        dispatcher.execute(replace(self.invocation, reference=51))
        self.assertEqual(calls, [(50, 1), (50, 2), (50, 3), (51, 1), (51, 3)])
