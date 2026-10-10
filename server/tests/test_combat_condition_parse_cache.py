"""Private syntax reuse never caches live native condition outcomes."""
import ast
from dataclasses import replace
import unittest
from unittest.mock import patch
from wakfu_server.combat_conditions import (
    _cached_condition_root,
    _condition_root,
    evaluate_condition,
    ConditionActor,
    ConditionContext,
    UnknownCondition,
)
from wakfu_server.combat_local_criteria import parse_local_criterion


class ConditionParseCacheTests(unittest.TestCase):
    def setUp(self):
        _cached_condition_root.cache_clear()

    def test_parse_reuse_still_evaluates_fresh_state_and_deck(self):
        expression = "HasState(7) and IsSpellInDeck(8)"
        actor = ConditionActor(frozenset({7}), frozenset({8}), frozenset(), True)
        with patch("wakfu_server.combat_conditions.canonical_aliases", return_value={}):
            self.assertTrue(
                evaluate_condition(expression, ConditionContext({"caster": actor}))
            )
            self.assertFalse(
                evaluate_condition(
                    expression,
                    ConditionContext({"caster": replace(actor, state_ids=frozenset())}),
                )
            )
            self.assertFalse(
                evaluate_condition(
                    expression,
                    ConditionContext(
                        {"caster": replace(actor, deck_spell_ids=frozenset())}
                    ),
                )
            )
        self.assertEqual(_cached_condition_root.cache_info().misses, 1)
        self.assertEqual(_cached_condition_root.cache_info().hits, 2)

    def test_public_parser_returns_fresh_mutable_trees(self):
        cached = _condition_root("True")
        public = parse_local_criterion("True")
        public.value = False
        self.assertTrue(cached.value)
        self.assertTrue(parse_local_criterion("True").value)

    def test_cache_bounds_large_syntax_and_invalid_syntax(self):
        for identity in range(600):
            _condition_root(str(identity))
        self.assertEqual(_cached_condition_root.cache_info().currsize, 512)
        _cached_condition_root.cache_clear()
        expression = " or ".join(["False"] * 260)
        root = _condition_root(expression)
        self.assertGreater(len(list(ast.walk(root))), 256)
        self.assertEqual(_cached_condition_root.cache_info().currsize, 0)
        _condition_root("True" + " " * 2050)
        self.assertEqual(_cached_condition_root.cache_info().currsize, 0)
        for _ in range(2):
            with self.assertRaises(UnknownCondition):
                evaluate_condition("HasState(", ConditionContext({}))
        self.assertEqual(_cached_condition_root.cache_info().currsize, 0)


if __name__ == "__main__":
    unittest.main()
