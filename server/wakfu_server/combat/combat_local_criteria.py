"""Restricted native eQd local expression aliases and alE/alF conditionals.

Assignments bind expression trees at parse time, including the previous binding
on reassignment. They do not execute statements or cache runtime numeric values.
Native SHARP markers wrap individual expressions, including multiple operands;
their alS.cK(false) localization metadata does not rebind predicate arguments.
"""
import ast
import copy
import io
import tokenize


class LocalCriterionSyntax(ValueError):
    pass


_MARKER = "@"
_MARKER_CALL = "__wakemu_native_sharp__"
_BOOLEAN_LITERALS = {"true": "True", "True": "True", "false": "False", "False": "False"}
_OPERATORS = frozenset(
    ("and", "or", "not", "+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">=", "!")
)


def _mask_markers(source):
    """Keep SHARP outside strings from becoming a Python comment token."""
    result = []
    pos = 0
    while pos < len(source):
        char = source[pos]
        if char in ("'", '"'):
            end = pos + 1
            delimiter = char
            if source.startswith(char * 3, pos):
                delimiter = char * 3
                end = pos + 3
            while end < len(source):
                if source[end] == "\\":
                    end += 2
                elif source.startswith(delimiter, end):
                    end += len(delimiter)
                    break
                else:
                    end += 1
            else:
                raise LocalCriterionSyntax("Unterminated native criterion string")
            result.append(source[pos:end])
            pos = end
            continue
        if char == _MARKER:
            raise LocalCriterionSyntax("Reserved native marker token")
        result.append(_MARKER if char == "#" else char)
        pos += 1
    return "".join(result)


def parse_local_criterion(source):
    if len(source) > 32768:
        raise LocalCriterionSyntax("Native criterion exceeds restricted size")
    try:
        lexical = [
            t
            for t in tokenize.generate_tokens(
                io.StringIO(_mask_markers(source)).readline
            )
            if not (t.type == tokenize.ERRORTOKEN and t.string.isspace())
            and t.type
            not in (
                tokenize.NEWLINE,
                tokenize.NL,
                tokenize.ENDMARKER,
                tokenize.INDENT,
                tokenize.DEDENT,
            )
        ]
        # Native eQb decimal integers accept leading zeroes (GetDate(06,...)).
        # Python tokenize splits 06 into adjacent NUMBER tokens; join only
        # physically adjacent decimal digits, never strings or spaced numbers.
        normalized = []
        for token in lexical:
            if (
                normalized
                and token.type == tokenize.NUMBER
                and token.string.isascii()
                and token.string.isdigit()
                and normalized[-1].type == tokenize.NUMBER
                and normalized[-1].string.isascii()
                and normalized[-1].string.isdigit()
                and normalized[-1].end == token.start
            ):
                previous = normalized.pop()
                token = previous._replace(
                    string=previous.string + token.string, end=token.end
                )
            normalized.append(token)
        tokens = [
            str(int(t.string, 10))
            if t.type == tokenize.NUMBER and t.string.isascii() and t.string.isdigit()
            else _BOOLEAN_LITERALS.get(t.string, t.string)
            if t.type == tokenize.NAME
            else t.string
            for t in normalized
        ]
        if _MARKER_CALL in tokens:
            raise LocalCriterionSyntax("Reserved native marker function")
        if len(tokens) > 4096:
            raise LocalCriterionSyntax(
                "Native criterion exceeds restricted token count"
            )
        pos = 0

        def expression(stops=()):
            nonlocal pos
            pieces = []
            while pos < len(tokens):
                token = tokens[pos]
                if token in stops and not (
                    token == _MARKER and (not pieces or pieces[-1] in _OPERATORS)
                ):
                    break
                pos += 1
                if token in ("!", "not"):
                    # eQb uses the same NOT token for ! and textual not.
                    # Group its native primary operand so comparison operators
                    # cannot silently become part of Python's lower-binding not.
                    pieces.append(f"(not {prefix_operand()})")
                elif token == _MARKER:
                    inside = expression((_MARKER,))
                    require(_MARKER)
                    pieces.append(f"{_MARKER_CALL}({inside})")
                elif token == "if":
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

        def prefix_operand():
            nonlocal pos
            if pos == len(tokens):
                raise LocalCriterionSyntax("Missing native negation operand")
            token = tokens[pos]
            pos += 1
            if token in ("!", "not"):
                return f"(not {prefix_operand()})"
            if token == "(":
                inside = expression((")",))
                require(")")
                return f"({inside})"
            if token == _MARKER:
                inside = expression((_MARKER,))
                require(_MARKER)
                return f"{_MARKER_CALL}({inside})"
            if token == "if":
                raise LocalCriterionSyntax(
                    "Native negation requires a grouped conditional"
                )
            if token in _OPERATORS or token in (";", ",", ")", "then", "else"):
                raise LocalCriterionSyntax("Invalid native negation operand")
            if token.isidentifier() and pos < len(tokens) and tokens[pos] == "(":
                pos += 1
                inside = (
                    ""
                    if pos < len(tokens) and tokens[pos] == ")"
                    else expression((")",))
                )
                require(")")
                return f"{token}({inside})"
            return token

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
                if node.func.id == _MARKER_CALL:
                    if len(node.args) != 1:
                        raise LocalCriterionSyntax("Invalid native marker expression")
                    if isinstance(node.args[0], ast.Tuple) and not node.args[0].elts:
                        raise LocalCriterionSyntax("Empty native marker expression")
                    expression = self.visit(node.args[0])
                    expression.native_localization_enabled = False
                    return expression
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
                if name in ("True", "False"):
                    raise LocalCriterionSyntax(
                        "Native boolean literal cannot be assigned"
                    )
                pos += 2
            translated = expression((";",))
            tree = Bind().visit(ast.parse(translated, mode="eval").body)
            if sum(1 for _ in ast.walk(tree)) > 8192:
                raise LocalCriterionSyntax("Expanded native criterion exceeds limit")
            if name is not None:
                bindings[name] = tree
                require(";")
                continue
            # eQd.fGv accepts a terminator on the final predicate too.
            # Preserve the one-predicate contract: no following statement or
            # empty extra statement is admitted after that terminator.
            if pos < len(tokens) and tokens[pos] == ";":
                pos += 1
            if pos != len(tokens):
                raise LocalCriterionSyntax("Only one final native predicate allowed")
            return tree
        raise LocalCriterionSyntax("Missing final native predicate")
    except (SyntaxError, tokenize.TokenError, RecursionError) as exc:
        raise LocalCriterionSyntax("Malformed native local criterion") from exc
