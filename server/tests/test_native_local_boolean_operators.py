import ast
import unittest

from wakfu_server.combat_local_criteria import (
    LocalCriterionSyntax,
    parse_local_criterion,
)


class NativeLocalBooleanOperatorTests(unittest.TestCase):
    def test_exact_installed_monster_criteria_parse(self):
        criteria = (
            '(HasState(3045,"target")&&!IsBreedId("target", 2819))||IsBreedId("target", 3267)',
            'HasState(3046,"caster")&&HasState(3045,"target")&&!(HasState(3046,"target")||HasState(3047,"target")||HasState(3048,"target"))',
        )
        for source in criteria:
            with self.subTest(source=source):
                self.assertIsNotNone(parse_local_criterion(source))

    def test_native_boolean_precedence_is_and_before_or(self):
        tree = parse_local_criterion("True || False && False")
        self.assertIsInstance(tree, ast.BoolOp)
        self.assertIsInstance(tree.op, ast.Or)
        self.assertIsInstance(tree.values[1], ast.BoolOp)
        self.assertIsInstance(tree.values[1].op, ast.And)

    def test_single_or_spaced_bitwise_operators_remain_rejected(self):
        for source in (
            "True & False",
            "True | False",
            "True & & False",
            "True | | False",
        ):
            with self.subTest(source=source), self.assertRaises(LocalCriterionSyntax):
                parse_local_criterion(source)


if __name__ == "__main__":
    unittest.main()
