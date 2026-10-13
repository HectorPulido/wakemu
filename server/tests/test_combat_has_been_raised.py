"""Native eMc reads the existing eGz.pHO component, never HP/history heuristics."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from wakfu_server.combat_restore_strategy import (
    initialize_restore_strategy,
    mark_restored_strategy,
    has_been_raised_by_effect,
)
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class HasBeenRaisedTests(unittest.TestCase):
    def test_fresh_and_actual_strategy_writer_are_independent_of_hp_and_death(self):
        actor = SimpleNamespace(hp=0)
        initialize_restore_strategy(actor)
        self.assertFalse(has_been_raised_by_effect(actor))
        preview = deepcopy(actor)
        mark_restored_strategy(preview)
        self.assertTrue(has_been_raised_by_effect(preview))
        self.assertFalse(has_been_raised_by_effect(actor))
        preview.hp = 120
        self.assertTrue(has_been_raised_by_effect(preview))

    def test_missing_or_invented_component_fails_closed(self):
        for value in (
            None,
            {"restored": False},
            {"source": "fresh.eGz.pHO", "restored": 0},
        ):
            with self.assertRaises(ValueError):
                has_been_raised_by_effect(
                    SimpleNamespace(native_restore_strategy=value)
                )

    def test_condition_requires_typed_query_and_literal_selector(self):
        actor = SimpleNamespace()
        initialize_restore_strategy(actor)
        seen = []
        context = ConditionContext(
            {},
            has_been_raised_query=lambda selector: seen.append(selector)
            or has_been_raised_by_effect(actor),
        )
        self.assertFalse(evaluate_condition('HasBeenRaisedByEffect("caster")', context))
        mark_restored_strategy(actor)
        self.assertTrue(evaluate_condition('HasBeenRaisedByEffect("target")', context))
        self.assertEqual(seen, ["caster", "target"])
        for expression, ctx in (
            ("HasBeenRaisedByEffect()", context),
            ("HasBeenRaisedByEffect(1)", context),
            ('HasBeenRaisedByEffect("caster")', ConditionContext({})),
            (
                'HasBeenRaisedByEffect("caster")',
                ConditionContext({}, has_been_raised_query=lambda _: 1),
            ),
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ctx)
