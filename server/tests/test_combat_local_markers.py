"""Native SHARP operands preserve syntax, selectors and explicit unknowns."""
import ast
import unittest

from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_local_criteria import (
    LocalCriterionSyntax,
    parse_local_criterion,
)


class NativeLocalMarkerTests(unittest.TestCase):
    def test_multiple_markers_preserve_boolean_grouping_and_precedence(self):
        context = ConditionContext({})
        for source, expected in (
            ("#(True)#", True),
            ("#True#", True),
            ("#(False)# or #(True)#", True),
            ("#(True)# and #(False)#", False),
            ("#(True)# or #(False)# and #(False)#", True),
            ("#(#True#)#", True),
            ("#(if (True) then (True) else (False))#", True),
        ):
            with self.subTest(source=source):
                self.assertEqual(evaluate_condition(source, context), expected)

    def test_marked_subtrees_keep_explicit_localization_metadata(self):
        root = parse_local_criterion("#IsEnemy()# or #HasState(1, 'target')#")
        self.assertIsInstance(root, ast.BoolOp)
        self.assertTrue(
            all(node.native_localization_enabled is False for node in root.values)
        )
        self.assertEqual(
            [node.func.id for node in root.values], ["IsEnemy", "HasState"]
        )
        self.assertEqual(root.values[1].args[1].value, "target")

    def test_aliases_keep_the_binding_visible_before_reassignment(self):
        source = "a = 2; b = a; a = 3; #(b == 2)# and #((a + 1) == 4)#"
        self.assertTrue(evaluate_condition(source, ConditionContext({})))

    def test_enemy_and_non_enemy_branches_keep_caster_target_state_bindings(self):
        source = (
            '#(IsEnemy() and HasState(4801, "target"))# or '
            '#(not IsEnemy() and HasState(4801, "caster"))#'
        )
        for affiliation, caster_states, target_states, expected in (
            (1, (), (4801,), True),
            (1, (4801,), (), False),
            (0, (4801,), (), True),
            (0, (), (4801,), False),
        ):
            context = ConditionContext(
                {
                    "caster": ConditionActor(
                        state_ids=frozenset(caster_states), fight_affiliation=0
                    ),
                    "target": ConditionActor(
                        state_ids=frozenset(target_states),
                        fight_affiliation=affiliation,
                    ),
                }
            )
            with self.subTest(
                affiliation=affiliation, caster=caster_states, target=target_states
            ):
                self.assertEqual(evaluate_condition(source, context), expected)

    def test_missing_authority_and_unsupported_hidden_branch_remain_unknown(self):
        for source in (
            "#IsEnemy()# or #True#",
            "#True# or #UnsupportedNative()#",
            '#(HasState(1, "target"))#',
        ):
            with self.subTest(source=source), self.assertRaises(UnknownCondition):
                evaluate_condition(source, ConditionContext({}))
        # Known but unused numeric authority still follows the existing lazy rule.
        self.assertTrue(
            evaluate_condition("#True# or #(GetLevel() > 0)#", ConditionContext({}))
        )

    def test_string_hashes_escapes_and_semicolon_are_not_rewritten(self):
        root = parse_local_criterion('Label("#tag#; \\"quoted\\" #")')
        self.assertEqual(root.args[0].value, '#tag#; "quoted" #')
        self.assertFalse(hasattr(root, "native_localization_enabled"))
        self.assertTrue(evaluate_condition("#True#;", ConditionContext({})))

    def test_unbalanced_or_incomplete_markers_never_become_python_comments(self):
        for source in (
            "#True",
            "True#",
            "#()#",
            "#True##False#",
            "#True# or #",
            "#(True#)",
            "True # ignored",
            "#True#; False",
            "#True#;;",
            "#True# #False#",
            "#(x = 1; True)#",
            'Label("unterminated#)',
            "__wakemu_native_sharp__(True)",
            "True \u00a7",
        ):
            with self.subTest(source=source), self.assertRaises(LocalCriterionSyntax):
                parse_local_criterion(source)

    def test_restricted_size_and_token_limits_still_apply(self):
        for source in ("#(" + " " * 32768 + "True)#", " or ".join(["#True#"] * 1500)):
            with self.assertRaises(LocalCriterionSyntax):
                parse_local_criterion(source)


if __name__ == "__main__":
    unittest.main()
