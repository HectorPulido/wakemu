import ast
import json
import unittest
from pathlib import Path
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_local_criteria import (
    parse_local_criterion,
    LocalCriterionSyntax,
)


class LocalCriteriaTests(unittest.TestCase):
    def test_native_boolean_literal_tokens_preserve_strings_and_aliases(self):
        context = ConditionContext({})
        for source, expected in (
            ("true", True),
            ("True", True),
            ("false", False),
            ("False", False),
            ("!false and not False", True),
            ("x = true; y = false; x and !y", True),
            ("trueish = false; falseValue = true; !trueish and falseValue", True),
            ("if (true) then (false) else (True)", False),
        ):
            with self.subTest(source=source):
                self.assertEqual(evaluate_condition(source, context), expected)
        tree = parse_local_criterion(
            'Fn("true", "false", "True", "False", true, false)'
        )
        self.assertEqual(
            [argument.value for argument in tree.args],
            ["true", "false", "True", "False", True, False],
        )
        tree = parse_local_criterion("IsOwnArea(true)")
        self.assertIs(tree.args[0].value, True)
        for source in ("TRUE", "FALSE", "tRue", "fAlse"):
            with self.subTest(source=source), self.assertRaises(UnknownCondition):
                evaluate_condition(source, context)
        for name in ("true", "false", "True", "False"):
            with self.subTest(name=name), self.assertRaisesRegex(
                LocalCriterionSyntax, "cannot be assigned"
            ):
                parse_local_criterion(f"{name} = False; {name}")

    def test_native_bang_negation_mixed_operators_and_primary_precedence(self):
        context = ConditionContext({})
        for source, expected in (
            ("!False", True),
            ("!!False", False),
            ("!False and True or False", True),
            ("!False or True and False", True),
            ("not !False", False),
            ("!not False", False),
            ("!(1 != 2)", False),
            ("!(1 == 2) and not False", True),
        ):
            with self.subTest(source=source):
                self.assertEqual(evaluate_condition(source, context), expected)
        # Native NOT binds to a primary; it cannot negate a numeric leaf and
        # silently turn into Python's not-of-comparison.
        for source in (
            "!1 == 2",
            "!False == True",
            "not 1 == 2",
            "not False == True",
            "not GetLevel() == 2",
            "x = 1; not x == 2",
            "x = False; not x == True",
            "!",
            "True and !",
            "!if (True) then (False) else (True)",
        ):
            with self.subTest(source=source), self.assertRaises(UnknownCondition):
                evaluate_condition(source, context)

    def test_bang_preserves_string_contents_and_not_equal_tokens(self):
        source = 'Fn("! not != #", "escaped\\"!", 1 != 2)'
        tree = parse_local_criterion(source)
        self.assertEqual(tree.args[0].value, "! not != #")
        self.assertEqual(tree.args[1].value, 'escaped"!')
        self.assertIsInstance(tree.args[2].ops[0], ast.NotEq)
        tree = parse_local_criterion('Fn("!", 1!=2)')
        self.assertEqual(tree.args[0].value, "!")
        self.assertIsInstance(tree.args[1].ops[0], ast.NotEq)

    def test_bang_alias_sharp_and_local_conditional(self):
        context = ConditionContext({})
        for source in (
            "x = !False; y = x; x = False; y and !x",
            "# !False # and !# False #",
            "!(if (True) then (False) else (True))",
            "if (!False) then (!True) else (!False)",
        ):
            tree = parse_local_criterion(source)
            self.assertIsNotNone(tree)
        self.assertTrue(
            evaluate_condition("x = !False; y = x; x = False; y and !x", context)
        )
        self.assertTrue(evaluate_condition("# !False # and !# False #", context))
        self.assertTrue(
            evaluate_condition("!(if (True) then (False) else (True))", context)
        )
        self.assertFalse(
            evaluate_condition("if (!False) then (!True) else (!False)", context)
        )
        localized = parse_local_criterion("!# False #")
        self.assertIs(localized.operand.native_localization_enabled, False)

    def test_actual_class_bang_criterion_is_parsed_without_reference_exception(self):
        tree = parse_local_criterion(
            'GetEffectCaster() != GetEffectTarget() and not IsCarrying("target") and !IsBreedId("target", 2382)'
        )
        calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call)}
        self.assertEqual(
            calls, {"GetEffectCaster", "GetEffectTarget", "IsCarrying", "IsBreedId"}
        )

    def test_final_native_semicolon_preserves_all_aliases_and_rejects_extra_predicate(
        self,
    ):
        context = ConditionContext({})
        self.assertTrue(evaluate_condition("a = 1; b = a + 2; b == 3;", context))
        self.assertTrue(evaluate_condition("True;", context))
        for source in ("a = 1; True; False", "True;;"):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(source, context)
        report = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "docs/reports/combat-inventory/ready-eca-deferred-runner-focal.json"
            ).read_text()
        )
        source = (
            report["rows"][0]["reason"]
            .removeprefix("Unsupported native criterion: ")
            .removesuffix(": Only one final native predicate allowed")
        )
        root = parse_local_criterion(source)
        calls = [node for node in ast.walk(root) if isinstance(node, ast.Call)]
        self.assertEqual(
            sum(node.func.id == "HasEffectWithSpecificId" for node in calls), 13
        )
        self.assertEqual(sum(node.func.id == "GetStateLevel" for node in calls), 1)

    def test_native_alias_binding_before_reassignment_and_long_overflow(self):
        c = ConditionContext({})
        self.assertTrue(evaluate_condition("a = 1; b = a; a = 2; b == 1 and a == 2", c))
        self.assertTrue(
            evaluate_condition(
                "n = 9223372036854775807; (n + 1) == (-9223372036854775807 - 1)", c
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("a == 2", c)

    def test_nested_conditional_and_missing_context_only_in_selected_branch(self):
        c = ConditionContext({})
        self.assertTrue(
            evaluate_condition(
                "n = if (False) then (GetLevel()) else if (True) then (2) else (3); n == 2",
                c,
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("n = if (True) then (GetLevel()) else (2); n == 2", c)
        self.assertTrue(
            evaluate_condition("if (True) then (True) else (IsCarried())", c)
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("if (True) then (True) else (Unsupported())", c)

    def test_mixed_numeric_if_uses_native_double_promotion(self):
        # alF.bDl requires BOTH numeric branches integral, even if one is unused.
        self.assertTrue(
            evaluate_condition(
                "n = if (True) then (9223372036854775807) else (1.5); (n + 1) > 0",
                ConditionContext({}),
            )
        )

    def test_real_feca6967_cost_all_four_decks_and_missing_authority(self):
        audit = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "docs/reports/combat-inventory/active-cast-audit.json"
            ).read_text()
        )

        def find(x):
            if isinstance(x, dict):
                if x.get("spell_id") == 6967 and x.get("reason", "").startswith(
                    "Unsupported native criterion: cost ="
                ):
                    return x["reason"].removeprefix("Unsupported native criterion: ")
                for value in x.values():
                    result = find(value)
                    if result:
                        return result
            if isinstance(x, list):
                for value in x:
                    result = find(value)
                    if result:
                        return result

        source = find(audit)
        self.assertIsNotNone(source)
        parse_local_criterion(
            source
        )  # Exact installed expression, including remaining predicate.
        assignment = source.split(";")[0] + "; "
        for ids, cost in (((), 2), ((6988,), 3), ((6994,), 0), ((6988, 6994), 1)):
            c = ConditionContext(
                {
                    "caster": ConditionActor(
                        deck_spell_ids=frozenset(ids),
                        excluded_deck_spell_ids=frozenset(),
                        is_player=True,
                    )
                }
            )
            self.assertTrue(evaluate_condition(assignment + f"cost == {cost}", c))
            with self.assertRaisesRegex(
                UnknownCondition, "Missing authoritative target cell"
            ):
                evaluate_condition(source, c)

    def test_no_python_execution_or_forward_aliases(self):
        for text in (
            "x = y; y = 1; True",
            'x = __import__("os").system("echo nope"); x == 0',
            "(lambda: True)()",
            "[x for x in []]",
            "x = 1;",
        ):
            with self.assertRaises((UnknownCondition, LocalCriterionSyntax)):
                evaluate_condition(text, ConditionContext({}))
