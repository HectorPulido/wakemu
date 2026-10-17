import unittest
from dataclasses import replace
from types import SimpleNamespace
import test_combat_maximum_resource as resource_tests
import test_combat_effect_dispatch as dispatch_tests
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_runner_callbacks import runner_value_scope
from wakfu_server.combat_stat_handler import StatExecutionContext


class MaximumLifecycleTests(unittest.TestCase):
    def fixture(self, mutate=None, *, retained=True):
        fixture = resource_tests.MaximumResourceTests()
        fixture.setUp()
        handler = fixture.handler
        handler.rng = lambda: 0
        phases = []
        handler.context = lambda *args: StatExecutionContext(
            True, True, None, retained, b"", None
        )

        class Events:
            def phase(self, effect, invocation, **kwargs):
                phases.append(
                    (
                        kwargs["channel"],
                        kwargs["uid"],
                        kwargs["value"],
                        kwargs["_event_ids"],
                    )
                )
                if mutate:
                    mutate(kwargs["channel"], kwargs["runner_modifier"], fixture)

            def register_applied(self, effect, invocation, uid):
                self.registered = uid

        handler.event_lifecycle = Events()
        effect = dispatch_tests.effect(41, (2, 1, 1))
        effect.update(native_effect_flags=[17], target_masks=[[] for _ in range(7)])
        return fixture, effect, phases

    def test_single_uid_l2_value_changes_application_and_final_observer(self):
        def mutation(channel, runner, fixture):
            if channel == 2:
                runner.mutate(1, 5, True)

        fixture, effect, phases = self.fixture(mutation)
        observed = []
        with runner_value_scope(
            lambda invocation, value: observed.append(value)
        ) as scope:
            invocation = replace(fixture.invocation, native_value_scope=scope)
            invocation = fixture.handler.prepare(effect, [], invocation)
            self.assertEqual(fixture.actor.max_mp, 3)
            self.assertTrue(fixture.handler(effect, [], invocation))
        self.assertEqual(fixture.actor.max_mp, 8)
        self.assertEqual([phase[0] for phase in phases], [1, 2, 3, 4])
        self.assertEqual([phase[2] for phase in phases], [0, 2, 5, 5])
        self.assertEqual({phase[1] for phase in phases}, {101})
        self.assertTrue(all(phase[3] == (0, 63) for phase in phases))
        self.assertEqual(observed, [5])
        self.assertEqual(fixture.handler.prepared_maxima, {})
        self.assertEqual(fixture.handler.runner_amounts, {})

    def test_l2_cancel_revalidates_before_raw_or_current_mutation(self):
        def mutation(channel, runner, fixture):
            if channel == 2:
                fixture.handler.context = lambda *args: StatExecutionContext(
                    False, True, None, True, b"", None
                )

        fixture, effect, phases = self.fixture(mutation)
        invocation = fixture.handler.prepare(effect, [], fixture.invocation)
        self.assertFalse(fixture.handler(effect, [], invocation))
        self.assertEqual((fixture.actor.mp, fixture.actor.max_mp), (3, 3))
        self.assertEqual(fixture.packets, [])
        self.assertEqual(fixture.fight.owned_stat_effects, {})
        self.assertEqual(fixture.handler.runner_amounts, {})
        self.assertEqual([phase[0] for phase in phases], [1, 2])

    def test_zero_mutation_suppresses_notification_but_runs_post_phases(self):
        fixture, effect, phases = self.fixture(
            lambda channel, runner, fixture: runner.mutate(1, 0, True)
            if channel == 2
            else None
        )
        invocation = fixture.handler.prepare(effect, [], fixture.invocation)
        self.assertTrue(fixture.handler(effect, [], invocation))
        self.assertEqual(fixture.actor.max_mp, 3)
        self.assertEqual(fixture.packets, [])
        self.assertEqual([phase[0] for phase in phases], [1, 2, 3, 4])
        self.assertEqual(fixture.fight.owned_stat_effects[101]["actual"], 0)

    def test_snapshot_is_read_after_l2_and_raw_effective_deltas_stay_distinct(self):
        fixture, effect, phases = self.fixture()
        actor = fixture.actor
        actor.effect_percentages[3] = 100
        actor.effect_maxima[3] = actor.max_mp = 6
        invocation = fixture.handler.prepare(effect, [], fixture.invocation)
        self.assertTrue(fixture.handler(effect, [], invocation))
        row = fixture.fight.owned_stat_effects[101]
        self.assertEqual((row["actual"], row["effective_delta"]), (2, 4))
        self.assertEqual((actor.effect_base_maxima[3], actor.max_mp), (5, 10))

    def test_dispatch_cancellations_and_errors_release_prepared_memory(self):
        for mode in ("condition", "probability", "error"):
            with self.subTest(mode=mode):
                fixture, effect, phases = self.fixture()
                effect["criteria"] = "1==0" if mode == "condition" else ""

                def condition(invocation):
                    if mode == "error":
                        raise ValueError("criteria authority failed")
                    return ConditionContext({})

                dispatcher = EffectDispatcher(
                    {"999": effect},
                    {41: fixture.handler},
                    resolve=lambda effect, invocation: (invocation,),
                    condition_context=condition,
                    probability_accepts=lambda *args: mode != "probability",
                    group_cells=lambda *args: (),
                    actor_position=lambda identity: fixture.actor.position,
                    prepare_effect=fixture.handler.prepare,
                )
                if mode == "error":
                    with self.assertRaisesRegex(ValueError, "criteria authority"):
                        dispatcher.execute(fixture.invocation)
                else:
                    self.assertFalse(dispatcher.execute(fixture.invocation))
                self.assertEqual(fixture.handler.prepared_maxima, {})
                self.assertEqual(fixture.handler.runner_amounts, {})
                self.assertEqual((fixture.actor.mp, fixture.actor.max_mp), (3, 3))
                self.assertEqual(fixture.packets, [])
                self.assertEqual(fixture.uid, 101)
                self.assertEqual([phase[0] for phase in phases], [1])

    def test_phase_error_releases_runner_without_rewinding_uid(self):
        def fail(channel, runner, fixture):
            if channel == 1:
                raise ValueError("native listener failed")

        fixture, effect, phases = self.fixture(fail)
        with self.assertRaisesRegex(ValueError, "listener"):
            fixture.handler.prepare(effect, [], fixture.invocation)
        self.assertEqual(
            (fixture.handler.prepared_maxima, fixture.handler.runner_amounts), ({}, {})
        )
        self.assertEqual(fixture.uid, 101)
