"""Condition evaluation releases its recursive helpers and native query owner."""
import gc
import unittest
import weakref
from unittest.mock import patch

from wakfu_server import combat_conditions as conditions


class QueryAuthority:
    def __init__(self):
        self.calls = []

    def query(self, *args):
        self.calls.append(args)
        return True


class ConditionContextLifetimeTests(unittest.TestCase):
    def setUp(self):
        gc.collect()

    def evaluate_and_release(self, expression, *, validate_only=False, rejects=False):
        owner = QueryAuthority()
        context = conditions.ConditionContext({}, line_of_sight_query=owner.query)
        context_ref, owner_ref = weakref.ref(context), weakref.ref(owner)
        # Literal criteria need no native characteristic aliases; this isolates
        # the evaluator's closure lifetime from loading the static catalog.
        with patch.object(conditions, "canonical_aliases", return_value={}):
            if rejects:
                with self.assertRaises(conditions.UnknownCondition):
                    conditions.evaluate_condition(
                        expression, context, validate_only=validate_only
                    )
            else:
                self.assertEqual(
                    conditions.evaluate_condition(
                        expression, context, validate_only=validate_only
                    ),
                    True if validate_only else expression == "True",
                )
        self.assertEqual(owner.calls, [])
        del context, owner
        self.assertIsNone(context_ref())
        self.assertIsNone(owner_ref())

    def test_successful_evaluation_releases_context_and_bound_authority(self):
        self.evaluate_and_release("True")
        self.evaluate_and_release("False")

    def test_validation_only_releases_context_without_executing_queries(self):
        self.evaluate_and_release("False", validate_only=True)

    def test_invalid_branch_releases_context_after_validation_rejection(self):
        self.evaluate_and_release("True or UnknownNativePredicate()", rejects=True)

    def test_missing_authority_releases_context_after_evaluation_rejection(self):
        self.evaluate_and_release("IsInAlignment()", rejects=True)
