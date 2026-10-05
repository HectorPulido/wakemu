import unittest
from types import SimpleNamespace
from wakfu_server.combat_active_spell import active_spell_id, active_spell_scope
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)


class ActiveSpellTests(unittest.TestCase):
    def test_current_scope_restores_even_on_failure_and_nested_cast(self):
        fight = SimpleNamespace(native_active_spell_id=None)
        self.assertEqual(active_spell_id(fight), -1)
        with active_spell_scope(fight, 6967):
            self.assertEqual(active_spell_id(fight), 6967)
            with self.assertRaises(ValueError):
                with active_spell_scope(fight, 5345):
                    self.assertEqual(active_spell_id(fight), 5345)
                    raise ValueError("rollback")
            self.assertEqual(active_spell_id(fight), 6967)
        self.assertIsNone(fight.native_active_spell_id)

    def test_generic_predicate_unknown_not_trigger_substitution(self):
        context = ConditionContext(actors={}, active_spell_id_query=lambda: 6967)
        self.assertTrue(evaluate_condition("GetActiveSpellId() == 6967", context))
        self.assertFalse(evaluate_condition("GetActiveSpellId() == 5345", context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetActiveSpellId() == 6967", ConditionContext(actors={})
            )
        with self.assertRaises(ValueError):
            active_spell_id(SimpleNamespace())
