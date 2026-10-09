import unittest
from types import SimpleNamespace as N
from dataclasses import replace
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_final_modifier import final_modifier_source
from wakfu_server.combat_runner_target import (
    bind_runner_target,
    redirect_source_runner,
    runner_target_invocation,
)
from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
from wakfu_server.combat_redirect_runner import NativeRedirectRunnerHandler
from wakfu_server.combat_stat_handler import StatExecutionContext
import test_combat_damage_handler as damage_fixture
import test_combat_healing_handler as healing_fixture


class RedirectRunnerTests(unittest.TestCase):
    def test_source_target_modes_preserve_caster_and_anchor(self):
        invocation = EffectInvocation(91, 20, 7, -7, (8, 9, 10))
        fight = N(actors={7: N(), -7: N()})
        for mode, expected in ((False, 7), (True, -7)):
            runner = NativeRunnerAmount(501, 1, rng=lambda: 0.5, value=40)
            bind_runner_target(runner, invocation)
            source = N(
                uid=501, effect_action_id=1, runner_modifier=runner, target_id=-7
            )
            with final_modifier_source(source):
                self.assertTrue(redirect_source_runner(fight, invocation, 100, mode))
            selected = runner_target_invocation(runner, invocation)
            self.assertEqual(
                (selected.target_id, selected.caster_id, selected.cell),
                (expected, 7, (8, 9, 10)),
            )
            self.assertEqual(runner.value, 40)

    def test_recalculation_and_stale_identity_fail_before_mutation(self):
        invocation = EffectInvocation(91, 20, 7, -7, (0, 0, 0))
        runner = NativeRunnerAmount(501, 1, rng=lambda: 0.5, value=40)
        bind_runner_target(runner, invocation)
        source = N(uid=501, effect_action_id=1, runner_modifier=runner, target_id=-7)
        with final_modifier_source(source):
            with self.assertRaisesRegex(ValueError, "recalculation authority"):
                redirect_source_runner(N(actors={7: N()}), invocation, -2, False)
            with self.assertRaisesRegex(ValueError, "Stale"):
                redirect_source_runner(
                    N(actors={7: N()}),
                    replace(invocation, native_trigger_context={"uid": 99}),
                    100,
                    False,
                )
        self.assertEqual(
            (runner.native_target_binding.target_id, runner.value), (-7, 40)
        )

    def test_damage_and_healing_consume_redirected_target(self):
        for fixture_class in (
            damage_fixture.DamageHandlerTests,
            healing_fixture.HealingHandlerTests,
        ):
            fixture = fixture_class()
            fixture.setUp()
            fight, handler = fixture.fight, fixture.handler
            original, destination = fight.actors[-7], fight.actors[7]
            if fixture_class is healing_fixture.HealingHandlerTests:
                destination.hp = 50
                destination.effect_stats.update(original.effect_stats)
                destination.effect_maxima.update(original.effect_maxima)
            else:
                destination.effect_stats[100] = 0
            before = (original.hp, destination.hp)
            reaction = NativeRedirectRunnerHandler(
                fight,
                fixture.packets,
                action_id=1,
                allocate_uid=lambda: 501,
                rng=lambda: 0.5,
                context=lambda *args: StatExecutionContext(
                    True, True, None, False, None
                ),
            )
            reaction_definition = dict(
                effect_class=1000,
                parameter_count=2,
                parameters=[100, 0, 0, 0],
                target_masks=[[], [], [], [], [], [], []],
            )

            class Events:
                def phase(_, definition, invocation, **data):
                    if data["channel"] == 2:
                        source = N(
                            uid=data["uid"],
                            effect_action_id=definition["effect_class"],
                            runner_modifier=data["runner_modifier"],
                            target_id=invocation.target_id,
                        )
                        with final_modifier_source(source):
                            self.assertTrue(
                                reaction(
                                    reaction_definition,
                                    {},
                                    replace(
                                        invocation,
                                        native_running_uid=None,
                                        native_trigger_context={"uid": data["uid"]},
                                    ),
                                )
                            )

            handler.event_lifecycle = Events()
            self.assertTrue(handler(fixture.effect, {}, fixture.invocation))
            self.assertEqual(original.hp, before[0])
            self.assertNotEqual(destination.hp, before[1])
            self.assertEqual((reaction.runners, reaction.prepared), ({}, {}))

    def test_handler_null_source_noop_still_delivers_and_cleans_preparation(self):
        fight = N(id=77, actors={7: N(), -7: N()}, owned_stat_effects={})
        packets = []
        handler = NativeRedirectRunnerHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 501,
            rng=lambda: 0.5,
            context=lambda *args: StatExecutionContext(True, True, None, False, None),
        )
        effect = dict(
            effect_class=1000,
            parameter_count=2,
            parameters=[100, 0, 0, 0],
            target_masks=[[], [], [], [], [], [], []],
        )
        invocation = EffectInvocation(91, 20, 7, -7, (0, 0, 0))
        prepared = handler.prepare(effect, {}, invocation)
        self.assertTrue(handler(effect, {}, prepared))
        self.assertEqual([kind for kind, _ in packets], [13497])
        self.assertEqual((handler.runners, handler.prepared), ({}, {}))
