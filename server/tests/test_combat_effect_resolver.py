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
    def test_removal_only_mask_does_not_defer_initial_application(self):
        self.effect["target_masks"][2] = [6, 7, 8]
        selected = self.resolver(self.effect, self.invocation)
        self.assertEqual([inv.target_id for inv in selected], [1, 2, 3])

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
        self.assertEqual(self.resolver(self.effect, empty), (empty,))

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
