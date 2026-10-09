"""Burst runners use native registered status rather than a blanket HP gate."""
import unittest

import test_combat_damage_handler as damage_fixture
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    global_fighter_guards,
)
from wakfu_server.combat_runner_target_life import verify_runner_target_life
from wakfu_server.combat_runner_target_life import runner_target_life_eligible
from wakfu_server.combat_global_pv_collections import set_global_fighter_status
from wakfu_server.combat_native_actor_lookup import native_actor_population
from wakfu_server.combat_effect_targets import select_native_effect_targets


class NativeRunnerTargetLifeTests(unittest.TestCase):
    def setUp(self):
        fixture = damage_fixture.DamageHandlerTests()
        fixture.setUp()
        self.fight, self.handler = fixture.fight, fixture.handler
        self.effect, self.invocation, self.packets = (
            fixture.effect,
            fixture.invocation,
            fixture.packets,
        )
        initialize_global_pv_collections(self.fight, tuple(self.fight.actors))

    def test_burst_kill_second_runner_delivers_without_duplicate_death(self):
        target = self.fight.actors[-7]
        target.effect_stats.update({92: 0, 97: 0})
        self.fight.actors[7].effect_stats[100] = 0
        with self.fight.effect_resolution():
            self.assertTrue(self.handler(self.effect, {}, self.invocation))
            self.assertEqual(target.hp, 0)
            self.assertTrue(global_fighter_guards(self.fight, target.id)["baG"])
            self.assertTrue(self.handler(self.effect, {}, self.invocation))
            deaths = [event for event in self.fight.events if event["kind"] == "death"]
            self.assertEqual(len(deaths), 1)
            self.assertEqual(len(self.packets), 2)

    def test_registered_hp0_in_play_stays_independent_of_hp(self):
        target = self.fight.actors[-7]
        target.hp = 0
        self.assertFalse(global_fighter_guards(self.fight, target.id)["baG"])
        verify_runner_target_life(
            self.fight, target, dict(effect_class=100, native_effect_flags=[])
        )
        self.assertTrue(self.handler(self.effect, {}, self.invocation))
        self.assertFalse(global_fighter_guards(self.fight, target.id)["baG"])
        self.assertFalse(any(event["kind"] == "death" for event in self.fight.events))

    def test_off_play_stat_requires_virtual_policy_or_flag15(self):
        target = self.fight.actors[-7]
        with self.fight.effect_resolution():
            self.fight.apply_effect_damage(7, -7, 100)
            with self.assertRaisesRegex(ValueError, "Dynamic native corpse guard"):
                verify_runner_target_life(
                    self.fight, target, dict(effect_class=100, native_effect_flags=[])
                )
            verify_runner_target_life(
                self.fight, target, dict(effect_class=100, native_effect_flags=[15])
            )
            with self.assertRaisesRegex(ValueError, "Target is not alive"):
                self.fight.apply_effect_damage(7, -7, 0)

    def test_native_fah_population_keeps_real_off_play_corpse_until_out_of_play(self):
        target = self.fight.actors[-7]
        with self.fight.effect_resolution():
            self.effect["effect_class"] = 1083
            self.fight.actors[7].effect_stats.update({21: 0, 22: 100, 23: 0, 24: 0})
            self.assertTrue(self.handler(self.effect, {}, self.invocation))
        self.assertEqual(target.hp, 0)
        self.assertTrue(global_fighter_guards(self.fight, target.id)["baG"])
        self.assertIn(target, native_actor_population(self.fight))

        caster = self.fight.actors[7]
        context = {
            7: dict(
                is_eGj=True,
                is_Qq=False,
                bEe=True,
                UNTARGETTABLE_BY_OTHER=False,
            ),
            -7: dict(
                is_eGj=True,
                is_Qq=False,
                bEe=True,
                is_eHH=True,
                UNTARGETTABLE_BY_OTHER=False,
                buX=False,
                baF=False,
                baG=True,
                baK=False,
            ),
        }
        recall = dict(
            effect_class=859,
            variant=0,
            native_effect_flags=[15],
            native_target_selector={"class": "fcE", "mask": 1},
            target_masks=(None,) * 7,
            area_class="anD",
            area_native="point",
        )
        selected = select_native_effect_targets(
            recall,
            caster,
            target.position,
            native_actor_population(self.fight),
            native_context=context,
        )
        self.assertIn(target, selected)
        verify_runner_target_life(self.fight, target, recall)
        with self.assertRaisesRegex(ValueError, "corpse guard"):
            verify_runner_target_life(
                self.fight, target, {**recall, "native_effect_flags": []}
            )

        set_global_fighter_status(self.fight, target.id, "OUT_OF_PLAY")
        self.assertNotIn(target, native_actor_population(self.fight))
        self.assertEqual(
            select_native_effect_targets(
                recall,
                caster,
                target.position,
                native_actor_population(self.fight),
                native_context=context,
            ),
            (),
        )

    def test_actual_state_handler_skips_proven_bcd_false_without_allocating_uid(self):
        from wakfu_server.combat_state_handler import (
            NativeStateHandler,
            StateCarrierContext,
        )
        from wakfu_server.combat_global_pv_collections import set_global_fighter_status

        target = self.fight.actors[-7]
        target.hp = 0
        set_global_fighter_status(self.fight, target.id, "OFF_PLAY")
        self.fight.native_active_spell_id = 123
        self.fight.native_active_spell_container = {"type": 25}
        effect = {
            "effect_class": 304,
            "native_effect_flags": [],
            "target_masks": (None, None, None, None, None, None, None),
        }
        invocation = self.invocation
        allocations = []
        handler = NativeStateHandler(
            self.fight,
            [],
            {},
            action_id=1,
            allocate_uid=lambda: allocations.append(True) or 500,
            context=lambda *_: self.fail("No carrier context is needed for a skip"),
            execute_child=lambda *_: self.fail("A skipped state has no children"),
        )
        context = StateCarrierContext(
            1, 0, False, None, None, False, False, False, 0, None
        )
        events_before = list(self.fight.events)
        self.assertFalse(
            handler.apply_reference(
                effect, invocation, 3442, 1, carrier_context=context
            )
        )
        self.assertEqual(allocations, [])
        self.assertEqual(target.state_ledger.entries, ())
        self.assertEqual(self.fight.events, events_before)

    def test_dispatcher_native_eligibility_distinguishes_skip_unknown_and_execute(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_conditions import ConditionContext
        from wakfu_server.combat_global_pv_collections import set_global_fighter_status

        target = self.fight.actors[-7]
        target.hp = 0
        set_global_fighter_status(self.fight, target.id, "OFF_PLAY")
        effect = {
            "effect_class": 304,
            "parameters": [1, 0],
            "parameter_count": 1,
            "probability_base": 100,
            "probability_per_level": 0,
            "minimum_level": 1,
            "maximum_level": 200,
            "criteria": "",
            "children": [],
            "native_effect_flags": [],
            "target_masks": (None, None, None, None, None, None, None),
        }
        handler = type(
            "GuardedHandler",
            (),
            {
                "native_eligibility": lambda _self, definition, selected: runner_target_life_eligible(
                    self.fight,
                    self.fight.actors[selected.target_id],
                    definition,
                    invocation=selected,
                ),
                "__call__": lambda _self, *_: calls.append("execute") is None,
            },
        )()
        calls, preparations = [], []

        def make_dispatcher():
            return EffectDispatcher(
                {"339483": effect},
                {304: handler},
                resolve=lambda _effect, selected: (selected,),
                condition_context=lambda _selected: ConditionContext({}),
                probability_accepts=lambda *_: True,
                group_cells=lambda *_: (),
                actor_position=lambda identity: self.fight.actors[identity].position,
                prepare_effect=lambda _effect, _values, selected: preparations.append(
                    "prepare"
                )
                or selected,
            )

        self.fight.native_active_spell_id = 123
        self.assertFalse(make_dispatcher().execute(self.invocation))
        self.assertEqual((preparations, calls), ([], []))

        del self.fight.native_active_spell_id
        with self.assertRaisesRegex(ValueError, "Dynamic native corpse guard"):
            make_dispatcher().execute(self.invocation)
        self.assertEqual((preparations, calls), ([], []))

        effect["native_effect_flags"] = [15]
        self.assertTrue(make_dispatcher().execute(self.invocation))
        self.assertEqual((preparations, calls), (["prepare"], ["execute"]))

    def test_wrapped_stat_corpse_rejection_skips_before_uid_and_preserves_unknown(self):
        from wakfu_server.combat_stat_handler import NativeStatHandler
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_conditions import ConditionContext

        effect = dict(
            effect_class=174,
            parameters=[1, 0],
            parameter_count=1,
            probability_base=100,
            probability_per_level=0,
            minimum_level=1,
            maximum_level=200,
            criteria="",
            children=[],
            native_effect_flags=[],
            target_masks=(None,) * 7,
        )
        handler = NativeStatHandler(
            self.fight,
            [],
            {"effects": {}},
            action_id=1,
            allocate_uid=lambda: self.fail("Skipped runner allocated UID"),
            context=lambda *_: self.fail("Skipped runner calculated PA"),
        )
        retention = object.__new__(NativeRetainedRuntime)
        wrapped = retention.wrap(handler)
        dispatcher = EffectDispatcher(
            {str(self.invocation.reference): effect},
            {174: wrapped},
            resolve=lambda _effect, selected: (selected,),
            condition_context=lambda *_: ConditionContext({}),
            probability_accepts=lambda *_: True,
            group_cells=lambda *_: (),
            actor_position=lambda key: self.fight.actors[key].position,
            prepare_effect=lambda *_: self.fail("Skipped runner prepared"),
        )
        with self.fight.effect_resolution():
            self.fight.apply_effect_damage(7, -7, 100)
            self.fight.native_active_spell_id = 7359
            self.assertFalse(dispatcher.execute(self.invocation))
            self.assertFalse(handler(effect, {}, self.invocation))
            effect["native_effect_flags"] = [15]
            self.assertTrue(wrapped.native_eligibility(effect, self.invocation))
            effect["native_effect_flags"] = []
            del self.fight.native_active_spell_id
            with self.assertRaisesRegex(ValueError, "Dynamic native corpse guard"):
                dispatcher.execute(self.invocation)

    def test_resource_loss_48_55_prepare_is_skipped_before_uid_or_lifecycle(self):
        from wakfu_server.combat_resource_loss_handler import NativeResourceLossHandler
        from wakfu_server.combat_global_pv_collections import set_global_fighter_status

        target = self.fight.actors[-7]
        target.hp = 0
        set_global_fighter_status(self.fight, target.id, "OFF_PLAY")
        self.fight.native_active_spell_id = 123
        allocated, phases = [], []
        handler = NativeResourceLossHandler(
            self.fight,
            [],
            action_id=1,
            allocate_uid=lambda: allocated.append(True) or 500,
            context=lambda *_: self.fail("Skipped eVZ must not resolve its plan"),
            rng=lambda: 0.25,
            properties=lambda _actor: frozenset(),
            secondary_state=None,
            event_lifecycle=type(
                "Events", (), {"phase": lambda *_args, **_kwargs: phases.append(True)}
            )(),
        )
        for effect_class in (48, 55):
            effect = {
                "effect_class": effect_class,
                "native_effect_flags": [],
                "target_masks": (None, None, None, None, None, None, None),
            }
            self.assertFalse(handler.native_eligibility(effect, self.invocation))
            self.assertIs(handler.prepare(effect, {}, self.invocation), self.invocation)
        self.assertEqual((allocated, phases), ([], []))

        unknown = dict(effect, native_effect_flags=[])
        del self.fight.native_active_spell_id
        with self.assertRaisesRegex(ValueError, "Dynamic native corpse guard"):
            handler.prepare(unknown, {}, self.invocation)

        permitted = dict(unknown, native_effect_flags=[15])
        self.assertTrue(handler.native_eligibility(permitted, self.invocation))
