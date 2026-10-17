"""Shared bindings preserve native branch eligibility and actual handler routes."""
import unittest

from wakfu_server.combat_effect_dispatch import (
    EffectDispatcher,
    EffectInvocation,
    UnsupportedEffectExecution,
)
from wakfu_server.combat_conditions import ConditionContext


def definition(family, *, criterion="", minimum=1):
    return dict(
        effect_class=family,
        parameters=[],
        parameter_count=0,
        probability_base=100,
        probability_per_level=0,
        minimum_level=minimum,
        maximum_level=200,
        criteria=criterion,
        children=[],
    )


def dispatcher(definitions, handlers, *, targets=True):
    return EffectDispatcher(
        definitions,
        handlers,
        resolve=lambda effect, invocation: (invocation,) if targets else (),
        condition_context=lambda invocation: ConditionContext({}),
        probability_accepts=lambda *args: True,
        group_cells=lambda *args: (),
        actor_position=lambda identity: (0, 0, 0),
    )


class OperationDispatchTests(unittest.TestCase):
    def test_missing_operation_on_ineligible_branches_is_not_rejected(self):
        invocation = EffectInvocation(1, 20, 7, 8, (0, 0, 0))
        for row, targets in (
            (definition(999999, criterion="1 > 2"), True),
            (definition(999999, minimum=21), True),
            (definition(999999), False),
        ):
            with self.subTest(row=row, targets=targets):
                runtime = dispatcher({"1": row}, {}, targets=targets)
                self.assertFalse(runtime.execute(invocation))

    def test_eligible_missing_handler_still_fails(self):
        runtime = dispatcher({"1": definition(304)}, {})
        with self.assertRaisesRegex(UnsupportedEffectExecution, "No handler"):
            runtime.execute(EffectInvocation(1, 20, 7, 8, (0, 0, 0)))

    def test_unmodeled_existing_handler_keeps_native_execution(self):
        observed = []

        def execute(effect, values, invocation):
            observed.append(invocation.target_id)
            return True

        runtime = dispatcher({"1": definition(999999)}, {999999: execute})
        self.assertEqual(runtime.operation_contracts[999999].status, "unknown")
        self.assertTrue(runtime.execute(EffectInvocation(1, 20, 7, 8, (0, 0, 0))))
        self.assertEqual(observed, [8])

    def test_factory_wrapping_and_route_removal_override_old_binding(self):
        observed = []

        def initial(*args):
            self.fail("Old route must not survive factory wrapping")

        def wrapped(*args):
            observed.append("wrapped")
            return True

        routes = {304: initial}
        runtime = dispatcher({"1": definition(304)}, routes)
        routes[304] = wrapped
        invocation = EffectInvocation(1, 20, 7, 8, (0, 0, 0))
        self.assertTrue(runtime.execute(invocation))
        self.assertEqual(observed, ["wrapped"])
        del routes[304]
        with self.assertRaisesRegex(UnsupportedEffectExecution, "No handler"):
            runtime.execute(invocation)
