"""Restricted native eQd local expression aliases and alE/alF conditionals.

Assignments bind expression trees at parse time, including the previous binding
on reassignment. They do not execute statements or cache runtime numeric values.
"""
import ast
import copy
import io
import tokenize


class LocalCriterionSyntax(ValueError):
    pass


def parse_local_criterion(source):
    if len(source) > 32768:
        raise LocalCriterionSyntax("Native criterion exceeds restricted size")
    try:
        tokens = [
            t.string
            for t in tokenize.generate_tokens(io.StringIO(source).readline)
            if t.type
            not in (
                tokenize.NEWLINE,
                tokenize.NL,
                tokenize.ENDMARKER,
                tokenize.INDENT,
                tokenize.DEDENT,
            )
        ]
        if len(tokens) > 4096:
            raise LocalCriterionSyntax(
                "Native criterion exceeds restricted token count"
            )
        pos = 0

        def expression(stops=()):
            nonlocal pos
            pieces = []
            while pos < len(tokens) and tokens[pos] not in stops:
                token = tokens[pos]
                pos += 1
                if token == "if":
                    condition = expression(("then",))
                    require("then")
                    yes = expression(("else",))
                    require("else")
                    no = expression(stops)
                    pieces.append(f"({yes} if {condition} else {no})")
                elif token == "(":
                    inside = (
                        ""
                        if pos < len(tokens) and tokens[pos] == ")"
                        else expression((")",))
                    )
                    require(")")
                    pieces.append(f"({inside})")
                elif token in ("then", "else", ")"):
                    raise LocalCriterionSyntax("Unmatched native conditional/group")
                elif token == "<>":
                    pieces.append("!=")
                elif token == "<" and pos < len(tokens) and tokens[pos] == ">":
                    pos += 1
                    pieces.append("!=")
                else:
                    pieces.append(token)
            if not pieces:
                raise LocalCriterionSyntax("Empty native expression")
            return " ".join(pieces)

        def require(token):
            nonlocal pos
            if pos == len(tokens) or tokens[pos] != token:
                raise LocalCriterionSyntax(f"Missing native token {token}")
            pos += 1

        bindings = {}

        class Bind(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id in bindings:
                    return copy.deepcopy(bindings[node.id])
                raise LocalCriterionSyntax(f"Unbound native local variable: {node.id}")

            def visit_Call(self, node):
                if not isinstance(node.func, ast.Name) or node.keywords:
                    raise LocalCriterionSyntax(
                        "Only native named predicate calls allowed"
                    )
                node.args = [self.visit(arg) for arg in node.args]
                return node

        while pos < len(tokens):
            name = None
            if (
                pos + 1 < len(tokens)
                and tokens[pos].isidentifier()
                and tokens[pos + 1] == "="
            ):
                name = tokens[pos]
                pos += 2
            translated = expression((";",))
            tree = Bind().visit(ast.parse(translated, mode="eval").body)
            if sum(1 for _ in ast.walk(tree)) > 8192:
                raise LocalCriterionSyntax("Expanded native criterion exceeds limit")
            if name is not None:
                bindings[name] = tree
                require(";")
                continue
            if pos != len(tokens):
                raise LocalCriterionSyntax("Only one final native predicate allowed")
            return tree
        raise LocalCriterionSyntax("Missing final native predicate")
    except (SyntaxError, tokenize.TokenError, RecursionError) as exc:
        raise LocalCriterionSyntax("Malformed native local criterion") from exc
