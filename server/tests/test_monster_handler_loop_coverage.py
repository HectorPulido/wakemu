"""Static family coverage includes lexical constant-loop registrations."""
import ast
import unittest
from audit_monster_family_coverage import COMBAT, loop_registered_families


class HandlerLoopCoverage(unittest.TestCase):
    def families(self, source, constants=None):
        return loop_registered_families(ast.parse(source), constants or {})

    def test_current_order_hooks_are_registered(self):
        self.assertTrue(
            {327, 328, 342}
            <= loop_registered_families(
                ast.parse((COMBAT / "combat_effect_runtime.py").read_text()), {}
            )
        )

    def test_literal_and_named_constant_iterables_need_no_whitelist(self):
        self.assertEqual(
            self.families(
                "FAMILIES=(327,328)\nfor family in frozenset(FAMILIES)|{342}:\n handlers[family]=hook"
            ),
            {327, 328, 342},
        )

    def test_nested_shadow_restores_outer_binding(self):
        self.assertEqual(
            self.families(
                "for family in (327,):\n for family in (328,):\n  handlers[family]=inner\n handlers[family]=outer"
            ),
            {327, 328},
        )

    def test_wrapping_existing_handlers_does_not_invent_family(self):
        self.assertEqual(
            self.families(
                "for kind,handler in tuple(handlers.items()):\n handlers[kind]=wrap(handler)"
            ),
            set(),
        )

    def test_function_local_constants_do_not_leak(self):
        self.assertEqual(
            self.families(
                "def first():\n LOCAL=(327,)\ndef second():\n for family in LOCAL:\n  handlers[family]=hook"
            ),
            set(),
        )

    def test_unknown_rebinding_clears_previous_constant(self):
        self.assertEqual(
            self.families(
                "families=(327,)\nfamilies=dynamic()\nfor family in families:\n handlers[family]=hook"
            ),
            set(),
        )

    def test_scalar_handler_binding_rejected_explicitly(self):
        with self.assertRaisesRegex(ValueError, "handler family binding"):
            self.families("family=327\nhandlers[family]=hook")

    def test_boolean_family_rejected(self):
        with self.assertRaises(ValueError):
            self.families("for family in (True,327):\n handlers[family]=hook")


if __name__ == "__main__":
    unittest.main()
