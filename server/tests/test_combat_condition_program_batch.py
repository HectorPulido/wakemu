"""Prepared programs preserve the native whole-criterion exception boundary."""
from dataclasses import replace
import unittest
from unittest.mock import patch

import test_combat_condition_cell_batch as batch_fixture
from wakfu_server import combat_conditions as conditions
from wakfu_server.combat_native_criterion_failure import (
    NativeCriterionRuntimeFailure,
    evaluate_native_effect_condition,
)
from wakfu_server.combat_condition_selection_scope import (
    condition_actor_selection_scope,
)
from wakfu_server.combat_cell_group import select_cell_group


class ConditionProgramBatchTests(unittest.TestCase):
    def setUp(self):
        self.fixture = batch_fixture.CellBatchOwnedTests()
        self.fixture.setUp()

    def start(self, criteria):
        self.fixture.effect["criteria"] = criteria
        return self.fixture.frame()

    def test_lazy_one_program_uses_every_fresh_full_context_and_callback_order(self):
        criteria = (
            'GetEnnemyCountInRange(0,5,"target")>=1 and not IsOnBorderCell("target")'
        )
        frame = self.start(criteria)
        traces = []
        with frame, condition_actor_selection_scope(), patch.object(
            conditions,
            "prepare_operation_condition_program",
            wraps=conditions.prepare_operation_condition_program,
        ) as prepare:
            self.assertIsNone(frame.condition_program)
            for value in (0, 1, 2):
                full = frame.condition(self.fixture.original)
                trace = []

                def enemy(*args):
                    trace.append(("enemy", args))
                    return value

                def border(*args):
                    trace.append(("border", args))
                    return -1

                context = replace(
                    full, enemy_range_query=enemy, border_cell_query=border
                )
                expected = evaluate_native_effect_condition(criteria, context)
                original_trace = list(trace)
                trace.clear()
                self.assertEqual(
                    frame.evaluate(criteria, context, evaluate_native_effect_condition),
                    expected,
                )
                self.assertEqual(trace, original_trace)
                traces.append(trace)
            self.assertEqual(prepare.call_count, 1)
            saved = frame.condition_program
        self.assertEqual([len(t) for t in traces], [1, 2, 2])
        self.assertIsNone(frame.condition_program)
        with self.assertRaisesRegex(RuntimeError, "Closed"):
            saved.evaluate(context)

    def test_native_runtime_failure_rejects_whole_not_or_criterion(self):
        cases = (
            ("not HasLineOfSight() or True", "line_of_sight_query"),
            ('GetEnnemyCountInRange(0,5,"target")==0 or True', "enemy_range_query"),
            ('not IsOnBorderCell("target") or True', "border_cell_query"),
        )
        for criteria, field in cases:
            with self.subTest(criteria=criteria):
                frame = self.start(criteria)
                with frame, condition_actor_selection_scope():
                    context = frame.condition(self.fixture.original)

                    def failed(*args):
                        raise NativeCriterionRuntimeFailure(
                            "Actual native evaluator exception"
                        )

                    context = replace(context, **{field: failed})
                    self.assertFalse(
                        evaluate_native_effect_condition(criteria, context)
                    )
                    self.assertFalse(
                        frame.evaluate(
                            criteria, context, evaluate_native_effect_condition
                        )
                    )
                    self.assertIsNotNone(frame.condition_program)

    def test_custom_evaluator_declines_batch_and_keeps_original_callback(self):
        criteria = 'GetEnnemyCountInRange(0,5,"target")>=0'
        observed = []

        def custom(text, context):
            observed.append((text, context))
            return True

        self.assertIsNone(
            self.fixture.factory(
                self.fixture.effect,
                self.fixture.original,
                activation=None,
                evaluator=custom,
            )
        )
        frame = self.start(criteria)
        with frame, condition_actor_selection_scope(), patch.object(
            conditions,
            "prepare_operation_condition_program",
            side_effect=AssertionError("Custom evaluator"),
        ):
            context = frame.condition(self.fixture.original)
            self.assertTrue(frame.evaluate(criteria, context, custom))
            self.assertIsNone(frame.condition_program)
        self.assertEqual(observed, [(criteria, context)])

    def test_original_full_context_failure_precedes_program_preparation(self):
        frame = self.start("HasLineOfSight()")
        with patch.object(
            conditions,
            "prepare_operation_condition_program",
            side_effect=AssertionError("Too early"),
        ) as prepare:
            with self.assertRaisesRegex(ValueError, "retained prefix"), frame:
                with patch(
                    "wakfu_server.combat_retained_runtime.native_retained_condition_reader",
                    side_effect=ValueError("retained prefix"),
                ):
                    context = frame.condition(self.fixture.original)
                    frame.evaluate(
                        "HasLineOfSight()", context, evaluate_native_effect_condition
                    )
            self.assertEqual(prepare.call_count, 0)
        self.assertIsNone(frame.condition_program)

    def test_custom_inner_evaluator_declines_and_releases_existing_program(self):
        from wakfu_server import combat_qi_fight

        criteria = 'GetEnnemyCountInRange(0,5,"target")>=0'
        frame = self.start(criteria)
        trace = []
        with frame, condition_actor_selection_scope():
            context = frame.condition(self.fixture.original)
            self.assertTrue(
                frame.evaluate(criteria, context, evaluate_native_effect_condition)
            )
            saved = frame.condition_program

            def custom(text, current):
                trace.append((text, current))
                return False

            with patch.object(conditions, "evaluate_condition", custom):
                self.assertIsNone(
                    conditions.prepare_operation_condition_program(criteria, context)
                )
                self.assertEqual(trace, [])
                self.assertIsNone(
                    self.fixture.factory(
                        self.fixture.effect, self.fixture.original, activation=None
                    )
                )
                self.assertFalse(
                    frame.evaluate(criteria, context, evaluate_native_effect_condition)
                )
                self.assertFalse(frame.active)
                self.assertIsNone(frame.condition_program)
                self.assertIsNone(frame.range_population)
                with patch.object(
                    combat_qi_fight,
                    "current_registry",
                    wraps=combat_qi_fight.current_registry,
                ) as reads:
                    frame.condition(self.fixture.original)
                    self.assertEqual(reads.call_count, 2)
            self.assertEqual(trace, [(criteria, context)])
            with self.assertRaisesRegex(RuntimeError, "Closed"):
                saved.evaluate(context)

    def test_invalid_short_circuited_signature_still_raises_before_queries(self):
        criteria = 'False and GetEnnemyCountInRange("bad")>0'
        frame = self.start(criteria)
        with frame, condition_actor_selection_scope():
            context = frame.condition(self.fixture.original)
            for evaluate in (
                lambda: evaluate_native_effect_condition(criteria, context),
                lambda: frame.evaluate(
                    criteria, context, evaluate_native_effect_condition
                ),
            ):
                with self.assertRaises(conditions.UnknownCondition):
                    evaluate()
            self.assertIsNone(frame.range_population)

    def test_program_closed_before_rng_and_exception_unwind(self):
        criteria = 'GetEnnemyCountInRange(0,5,"target")>=0'
        frame = self.start(criteria)
        saved, draws = [], []

        def condition(cell):
            context = frame.condition(replace(self.fixture.original, cell=cell))
            result = frame.evaluate(criteria, context, evaluate_native_effect_condition)
            saved.append((frame.condition_program, context))
            return result

        def rng():
            self.assertFalse(frame.active)
            self.assertIsNone(frame.condition_program)
            self.assertIsNone(frame.range_population)
            draws.append(0.25)
            return 0.25

        select_cell_group(
            dict(parameters=[2, 0, 1, 0, 0, 0, 1]),
            [(2, 2, 0), (2, 3, 0), (3, 2, 0)],
            caster_position=(0, 0, 0),
            condition=condition,
            rng=rng,
            reuse_condition_actors=True,
            condition_batch=frame,
        )
        self.assertEqual(draws, [0.25, 0.25])
        for program, context in saved:
            with self.assertRaisesRegex(RuntimeError, "Closed"):
                program.evaluate(context)
        frame = self.start(criteria)
        with self.assertRaisesRegex(
            RuntimeError, "after evaluation"
        ), frame, condition_actor_selection_scope():
            context = frame.condition(self.fixture.original)
            frame.evaluate(criteria, context, evaluate_native_effect_condition)
            saved_program = frame.condition_program
            raise RuntimeError("after evaluation")
        self.assertIsNone(frame.condition_program)
        with self.assertRaisesRegex(RuntimeError, "Closed"):
            saved_program.evaluate(context)
