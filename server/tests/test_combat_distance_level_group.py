import unittest
from types import SimpleNamespace as N
from itertools import count
from unittest.mock import Mock
from wakfu_server.combat_distance_level_group import (
    distance_group_amount,
    NativeDistanceGroupRunner,
)
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_effect_groups import native_group_route
from test_combat_effect_dispatch import effect


class NativeDistanceLevelGroupTests(unittest.TestCase):
    def definition(self, factor=0.5, children=(91, 92), criteria=""):
        result = effect(1080, (factor,), children=children, criteria=criteria)
        result.update(
            target_masks=[[], [], [], [], [], [], []], native_effect_flags=[16]
        )
        return result

    def test_native_float_factor_manhattan_xy_floor_and_java_int_overflow(self):
        definition = self.definition()
        self.assertEqual(
            distance_group_amount(definition, 100, (0, 0, -100), (3, 4, 100)), 3
        )
        self.assertEqual(
            distance_group_amount(self.definition(1), 1, (0, 0, 0), (3, 4, 0)), 7
        )
        self.assertEqual(
            distance_group_amount(self.definition(-0.5), 1, (0, 0, 0), (3, 4, 0)), -4
        )
        self.assertEqual(
            distance_group_amount(
                self.definition(1), 1, (0, 0, 0), (-2147483648, 0, 0)
            ),
            -2147483648,
        )
        self.assertEqual(distance_group_amount(definition, 1, (3, 4, 0), (3, 4, 0)), 0)

    def test_child_context_is_original_ewd_context_without_flag16_override(self):
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.transmit_child_override = lambda *args: self.fail(
            "eYi SP must not be overwritten"
        )
        context = runtime.child_context(
            self.definition(), {}, N(), event_activation=True, native_override=3
        )
        self.assertEqual(context.hex(), "08001000200328013000380040004800")
        self.assertEqual(native_group_route(self.definition()), "cell")

    def test_child_sp_minus_one_uses_actual_container_and_other_ints_narrow(self):
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.container_level = lambda invocation: (True, 123)
        effect = self.definition(-0.5)
        override = distance_group_amount(effect, 20, (0, 0, 0), (1, 0, 0))
        self.assertEqual(override, -1)
        level, _ = runtime.child_level_context(
            effect, {}, N(), default_level=20, native_override=override
        )
        self.assertEqual(level, 123)
        level, _ = runtime.child_level_context(
            effect, {}, N(), default_level=20, native_override=65535
        )
        self.assertEqual(level, -1)
        runtime.container_level = lambda invocation: (False, None)
        level, _ = runtime.child_level_context(
            effect, {}, N(), default_level=20, native_override=-1
        )
        self.assertEqual(level, 0)

    def dispatcher(self, seen, trace, criteria=""):
        ids = count(501)
        runner = NativeDistanceGroupRunner(
            allocate_uid=lambda: next(ids),
            actor_position=lambda identity: (0, 0, 0),
            rng=lambda: 0.5,
        )
        lifecycle = Mock()
        lifecycle.phase.side_effect = lambda *args, **kw: trace.append(
            ("phase", kw["channel"], kw["value"])
        )
        runner.event_lifecycle = lifecycle

        def begin(*args, **kw):
            trace.append(("begin", kw["initial_value"], args[2].native_running_uid))
            return "pending"

        runtime = object.__new__(NativeRetainedRuntime)
        runtime.container_level = lambda invocation: (True, 20)
        retention = N(
            is_subscription=lambda *args: False,
            probability_bypassed=lambda *args: False,
            begin_group=begin,
            finish_group=lambda pending: trace.append(("finish", pending)),
            child_level_context=runtime.child_level_context,
        )

        def child(definition, values, invocation):
            seen.append(invocation)
            trace.append(("child", invocation.reference))
            return invocation.reference == 92

        dispatcher = EffectDispatcher(
            {
                "90": self.definition(criteria=criteria),
                "91": effect(400),
                "92": effect(400),
            },
            {1080: runner, 400: child},
            resolve=lambda e, inv: (inv,),
            condition_context=lambda inv: ConditionContext({}),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: self.fail("eWd does not expand its anchor"),
            actor_position=runner.actor_position,
            group_retention=retention,
            distance_group_runner=runner,
            prepare_effect=lambda e, v, inv: runner.prepare(e, v, inv)
            if e["effect_class"] == 1080
            else inv,
        )
        return dispatcher, runner

    def test_actual_dispatch_order_nullable_anchor_children_and_runner_cleanup(self):
        seen, trace = [], []
        dispatcher, runner = self.dispatcher(seen, trace)
        self.assertTrue(
            dispatcher.execute(EffectInvocation(90, 20, 7, None, (3, 4, 5)))
        )
        self.assertEqual(
            [
                (i.reference, i.level, i.target_id, i.cell, i.native_running_uid)
                for i in seen
            ],
            [(91, 3, None, (3, 4, 5), None), (92, 3, None, (3, 4, 5), None)],
        )
        self.assertEqual(
            trace,
            [
                ("phase", 1, 0),
                ("phase", 2, 3),
                ("begin", 3, 501),
                ("child", 91),
                ("child", 92),
                ("finish", "pending"),
                ("phase", 3, 3),
                ("phase", 4, 3),
            ],
        )
        self.assertEqual(runner.prepared, {})
        self.assertEqual(runner.runners, {})

    def test_rejected_criteria_cancels_native_preparation_without_children(self):
        seen, trace = [], []
        dispatcher, runner = self.dispatcher(seen, trace, criteria="False")
        self.assertFalse(
            dispatcher.execute(EffectInvocation(90, 20, 7, None, (3, 4, 5)))
        )
        self.assertEqual(seen, [])
        self.assertEqual(trace, [("phase", 1, 0)])
        self.assertEqual(runner.prepared, {})
        self.assertEqual(runner.runners, {})

    def test_event_clone_uses_one_allocated_uid_and_recalculates_before_l1(self):
        seen, trace = [], []
        dispatcher, runner = self.dispatcher(seen, trace)
        runner.allocate_uid = lambda: self.fail(
            "Native activation already allocated its clone"
        )
        draws = []
        invocation = EffectInvocation(90, 20, 7, None, (3, 4, 5))
        self.assertTrue(
            dispatcher.execute_activation(
                invocation,
                source=None,
                condition_context=lambda *args: ConditionContext({}),
                executable=True,
                allocate_uid=lambda: draws.append(777) or 777,
            )
        )
        self.assertEqual(draws, [777])
        self.assertEqual(trace[:2], [("phase", 1, 3), ("phase", 2, 3)])
        self.assertFalse(any(row[0] == "begin" for row in trace))
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(row.native_running_uid is None for row in seen))
        self.assertEqual(runner.prepared, {})
        self.assertEqual(runner.runners, {})
