"""Restricted installed transport predicates over server-owned facts and UTC time."""
import ast
import operator
import re

from wakfu_server.combat_local_criteria import parse_local_criterion
from wakfu_server.combat_inventory_date_conditions import calendar_milliseconds

_COMPARISONS = {
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}
_CALLS = {"GetRealLevel", "GetDate", "IsBefore", "IsAfter", "IsAchievementComplete"}


def evaluate(expression, character, *, now_ms, achievement_complete=None):
    """Unknown/malformed predicates raise; callers must reject the whole route.

    Validate every branch before evaluation, including branches made unreachable
    by False. No mission bypass, client facts or arbitrary Python evaluation.
    """
    if not isinstance(expression, str) or len(expression) > 32768:
        raise ValueError("Malformed transport criterion")
    if not expression.strip():
        return True
    if type(now_ms) is not int or not 0 <= now_ms < 2**63:
        raise ValueError("Missing authoritative transport clock")
    annotated = re.sub(
        r'@\("[^"\n]+"\)\s*([^@]+)@', lambda m: "(" + m[1] + ")", expression
    )
    if "@" in annotated:
        raise ValueError("Malformed transport criterion annotation")
    tree = parse_local_criterion(annotated)

    def check(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, bool):
            return
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            for value in node.values:
                check(value)
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            check(node.operand)
            return
        if isinstance(node, ast.Compare) and all(
            type(op) in _COMPARISONS for op in node.ops
        ):
            check(node.left)
            for value in node.comparators:
                check(value)
            return
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _CALLS
            and not node.keywords
        ):
            name, args = node.func.id, node.args
            if not all(
                isinstance(arg, ast.Constant) and type(arg.value) is int for arg in args
            ):
                raise ValueError("Transport arguments must be literal integers")
            if (
                name == "GetRealLevel"
                and not args
                or name == "GetDate"
                and len(args) in (0, 6)
                or name in ("IsBefore", "IsAfter")
                and len(args) == 6
                or name == "IsAchievementComplete"
                and len(args) == 1
                and 0 < args[0].value < 2**31
            ):
                return
        raise ValueError("Unsupported transport criterion")

    def boolean(value):
        if type(value) is not bool:
            raise ValueError("Transport predicate lacks boolean authority")
        return value

    def visit(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BoolOp):
            values = [boolean(visit(value)) for value in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp):
            return not boolean(visit(node.operand))
        if isinstance(node, ast.Compare):
            values = [visit(node.left)] + [visit(value) for value in node.comparators]
            if any(type(value) is not int for value in values):
                raise ValueError("Transport comparison requires integer authority")
            return all(
                _COMPARISONS[type(op)](left, right)
                for op, left, right in zip(node.ops, values, values[1:])
            )
        name, args = node.func.id, tuple(arg.value for arg in node.args)
        if name == "GetRealLevel":
            level = character.get("level")
            if type(level) is not int or level < 1:
                raise ValueError("Missing real transport level")
            return level
        if name == "GetDate":
            return now_ms if not args else calendar_milliseconds(args)
        if name in ("IsBefore", "IsAfter"):
            date = calendar_milliseconds(args)
            return now_ms < date if name == "IsBefore" else now_ms > date
        if not callable(achievement_complete):
            raise ValueError("Missing owned transport achievement authority")
        return boolean(achievement_complete(args[0]))

    check(tree)
    return boolean(visit(tree))


def evaluator(store, character):
    """One request clock and lazy immutable selected-owner achievement snapshot."""
    from wakfu_server.maps.dungeon_achievement_authority import queries

    now_ms = int(store.clock() * 1000)
    owner = character.get("id")
    if type(owner) is not int or owner <= 0:
        raise ValueError("Missing transport achievement owner")
    snapshot = None

    def completed(identity):
        nonlocal snapshot
        if snapshot is None:
            snapshot = queries(store, owner)
        return snapshot["IsAchievementComplete"](identity)

    def allowed(expression, actor):
        if actor.get("id") != owner:
            raise ValueError("Transport criterion owner changed")
        return evaluate(
            expression, actor, now_ms=now_ms, achievement_complete=completed
        )

    return allowed
