"""Operation-local criterion programs preserve fresh native query semantics."""
import gc
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import weakref
from wakfu_server import combat_conditions as s
from wakfu_server.combat_native_criterion_failure import (
    NativeCriterionRuntimeFailure,
    evaluate_native_effect_condition,
)

CRITERIA = json.loads(
    (
        Path(__file__).parent / "fixtures/actual_condition_program_criteria.json"
    ).read_text()
)["criteria"]


def ctx(trace, mode="pass"):
    def query(name, fn):
        def call(*args):
            trace.append((name, args))
            return fn(*args)

        return call

    return s.ConditionContext(
        actors={},
        target_cell=s.ConditionCell(mode != "blocked", False, ()),
        enemy_range_query=query(
            "enemy",
            lambda minimum, maximum, *args: 0
            if mode == "zero"
            else int(maximum == 5 or minimum in (1, 4)),
        ),
        allies_range_query=query("allies", lambda *args: 0),
        specific_area_range_query=query("specific", lambda *args: 0),
        border_cell_query=query("border", lambda *args: -1),
        line_of_sight_query=None
        if mode == "missing_los"
        else query("los", lambda: True),
    )


def outcome(call):
    try:
        return {"value": call()}
    except Exception as error:
        return {"error": type(error).__name__, "message": str(error)}


class OperationConditionProgramTests(unittest.TestCase):
    def test_actual_four_criteria_all_fresh_queries_values_and_errors(self):
        for reference, criteria in CRITERIA.items():
            trace = []
            first = ctx(trace)
            program = s.prepare_operation_condition_program(criteria, first)
            self.assertEqual(trace, [])
            try:
                for mode in ("pass", "zero", "blocked", "missing_los", "pass"):
                    old_trace = []
                    new_trace = []
                    old_context = ctx(old_trace, mode)
                    new_context = ctx(new_trace, mode)
                    old = outcome(lambda: s.evaluate_condition(criteria, old_context))
                    new = outcome(lambda: program.evaluate(new_context))
                    self.assertEqual(old, new, (reference, mode))
                    self.assertEqual(old_trace, new_trace, (reference, mode))
            finally:
                program.close()

    def test_unsupported_and_custom_context_fall_back_without_query(self):
        for criteria in (
            "False and GetRandomNumber(1)>0",
            'HasState(1978,"target")',
            "False and BogusUnsupported()",
            "HasLineOfSight(foo=1)",
            "HasLineOfSight(",
        ):
            trace = []
            context = ctx(trace)
            self.assertIsNone(s.prepare_operation_condition_program(criteria, context))
            self.assertEqual(trace, [])
        custom = SimpleNamespace(line_of_sight_query=lambda: True)
        self.assertIsNone(
            s.prepare_operation_condition_program("HasLineOfSight()", custom)
        )
        self.assertTrue(s.evaluate_condition("HasLineOfSight()", custom))

    def test_original_complete_validation_runs_before_first_callback(self):
        for criteria in (
            "HasLineOfSight(1)",
            "False and HasLineOfSight(1)",
            'IsTargetCellFree("bad")',
            "IsOnBorderCell()",
        ):
            trace = []
            context = ctx(trace)
            old = outcome(lambda: s.evaluate_condition(criteria, context))
            new = outcome(
                lambda: s.prepare_operation_condition_program(criteria, context)
            )
            self.assertEqual(old, new)
            self.assertEqual(trace, [])

    def test_context_is_detached_after_success_failure_and_close(self):
        first = ctx([])
        program = s.prepare_operation_condition_program("HasLineOfSight()", first)
        for mode in ("pass", "missing_los"):
            value = ctx([], mode)
            ref = weakref.ref(value)
            outcome(lambda: program.evaluate(value))
            del value
            gc.collect()
            self.assertIsNone(ref())
        ref = weakref.ref(first)
        del first
        gc.collect()
        self.assertIsNone(ref())
        program.close()
        program.close()
        self.assertRaises(RuntimeError, program.evaluate, ctx([]))

    def test_validate_only_never_invokes_query_or_converts_false_to_false(self):
        trace = []
        value = ctx(trace, "blocked")
        program = s.prepare_operation_condition_program(
            "IsTargetCellFree() and HasLineOfSight()", value
        )
        try:
            self.assertTrue(program.evaluate(value, validate_only=True))
            self.assertEqual(trace, [])
            self.assertFalse(program.evaluate(value))
            self.assertEqual(trace, [])
        finally:
            program.close()

    def test_reentry_fallback_does_not_overwrite_outer_context(self):
        criteria = "HasLineOfSight() and IsTargetCellFree()"
        program = s.prepare_operation_condition_program(criteria, ctx([]))
        inner = s.ConditionContext(
            actors={},
            target_cell=s.ConditionCell(False, False, ()),
            line_of_sight_query=lambda: False,
        )
        outer = s.ConditionContext(
            actors={},
            target_cell=s.ConditionCell(True, False, ()),
            line_of_sight_query=lambda: not program.evaluate(inner),
        )
        try:
            self.assertTrue(program.evaluate(outer))
        finally:
            program.close()

    def test_custom_inner_evaluator_falls_back_and_restored_source_prepares(self):
        canonical = s.evaluate_condition
        trace = []

        def custom(criteria, context, **options):
            trace.append((criteria, context, options))
            context.actors["custom_evaluator_marker"] = True
            return False

        s.evaluate_condition = custom
        try:
            context = ctx([])
            self.assertIsNone(
                s.prepare_operation_condition_program("HasLineOfSight()", context)
            )
            self.assertEqual(trace, [])
            self.assertNotIn("custom_evaluator_marker", context.actors)
            self.assertFalse(s.evaluate_condition("HasLineOfSight()", context))
            self.assertEqual(len(trace), 1)
            self.assertTrue(context.actors["custom_evaluator_marker"])
        finally:
            s.evaluate_condition = canonical
        program = s.prepare_operation_condition_program("HasLineOfSight()", ctx([]))
        try:
            self.assertTrue(program.evaluate(ctx([])))
        finally:
            program.close()

    def test_context_dependent_difficulty_and_random_are_not_prepared(self):
        trace = []
        value = s.ConditionContext(
            actors={},
            dungeon_difficulty_query=lambda: trace.append("difficulty") or 1,
            random_number_query=lambda *args: trace.append("random") or 0,
        )
        for criteria in (
            "GetDungeonDifficulty() > 0",
            "False and GetRandomNumber(1) > 0",
        ):
            self.assertIsNone(s.prepare_operation_condition_program(criteria, value))
            self.assertEqual(trace, [])


class NativeFailureBoundaryTests(unittest.TestCase):
    def context(self, trace):
        def fail(name):
            def callback(*args):
                trace.append((name, args))
                raise NativeCriterionRuntimeFailure("Proven native fixture failure")

            return callback

        return s.ConditionContext(
            actors={},
            border_cell_query=fail("border"),
            enemy_range_query=fail("enemy"),
            specific_area_range_query=fail("area"),
        )

    def test_program_preserves_whole_criterion_failure_at_native_boundary(self):
        cases = (
            'not IsOnBorderCell("target")',
            'IsOnBorderCell("target") or True',
            'not (GetEnnemyCountInRange(2,"target") > 0)',
            'GetEnnemyCountInRange(2,"target") > 0 or True',
            'not (GetSpecificEffectAreaCountInRange("target",2114,0,2) > 0)',
            'GetSpecificEffectAreaCountInRange("target",2114,0,2) > 0 or True',
            'False and IsOnBorderCell("target")',
            'True or IsOnBorderCell("target")',
        )
        for criteria in cases:
            with self.subTest(criteria=criteria):
                old_trace, new_trace = ([], [])
                old = evaluate_native_effect_condition(
                    criteria, self.context(old_trace)
                )
                first = self.context(new_trace)
                program = s.prepare_operation_condition_program(criteria, first)
                self.assertEqual(new_trace, [])
                try:
                    try:
                        new = program.evaluate(first)
                    except NativeCriterionRuntimeFailure:
                        new = False
                    self.assertEqual(old, new)
                    self.assertEqual(old_trace, new_trace)
                    if "False and" not in criteria and "True or" not in criteria:
                        self.assertFalse(new)
                        self.assertEqual(len(new_trace), 1)
                        with self.assertRaises(NativeCriterionRuntimeFailure):
                            program.evaluate(self.context([]))
                finally:
                    program.close()
