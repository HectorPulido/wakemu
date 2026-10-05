import random
import unittest
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.combat_ordinary_authority import native_random_number


class RandomConditionTests(unittest.TestCase):
    def test_ascending_candidates_and_duplicate_exclusions(self):
        actual = [
            native_random_number(6, (1, 3, 3, -1, 8), draw_index=lambda n, i=i: i)
            for i in range(4)
        ]
        self.assertEqual(actual, [0, 2, 4, 5])

    def test_limits_and_empty_do_not_draw(self):
        def forbidden(n):
            self.fail("Invalid range consumed random state")

        for limit, excluded in ((0, ()), (-1, ()), (2, (0, 1)), (2.0, ())):
            with self.assertRaises(ValueError):
                native_random_number(limit, excluded, draw_index=forbidden)
        self.assertEqual(native_random_number(1, (), draw_index=lambda n: 0), 0)

    def test_criterion_uses_owned_rng_once_and_short_circuits(self):
        draws = []
        context = ConditionContext(
            {},
            random_number_query=lambda limit, excluded: native_random_number(
                limit, excluded, draw_index=lambda n: draws.append(n) or 0
            ),
        )
        self.assertTrue(evaluate_condition("GetRandomNumber(5,[0,2]) == 1", context))
        self.assertEqual(draws, [3])
        self.assertTrue(evaluate_condition("True or GetRandomNumber(5) == 4", context))
        self.assertEqual(draws, [3])
        for criterion in (
            "GetRandomNumber(2.5)==0",
            "GetRandomNumber(5,[1.2])==0",
            "GetRandomNumber()==0",
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(criterion, context)

    def test_preview_rng_rollback_is_callers_owned_state(self):
        original = random.Random(4)
        before = original.getstate()
        preview = random.Random()
        preview.setstate(before)
        draw = lambda n: preview.randrange(n)
        native_random_number(10, (), draw_index=draw)
        self.assertEqual(original.getstate(), before)
        self.assertNotEqual(preview.getstate(), before)

    def test_observer_does_not_evaluate_random_criterion_again(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from audit_active_spells import observed

        class Handler:
            def apply_reference(self, *a, **kw):
                pass

        class Dispatcher:
            native_state_handler = Handler()

            def _diagnose(self, invocation, **details):
                pass

            def _execute(self, invocation):
                self._diagnose(
                    invocation,
                    status="skipped_condition",
                    criteria="GetRandomNumber(3)==2",
                )
                return False

        records = []
        dispatcher, _ = observed(lambda p, c: (Dispatcher(), []), records)(None, None)
        from types import SimpleNamespace

        dispatcher._execute(SimpleNamespace(reference=1, level=1))
        self.assertEqual(records[0], (1, "condition_false", "GetRandomNumber(3)==2"))
