"""Restricted native dungeon access predicates with explicit server authority."""
from __future__ import annotations


SETTING = "dungeon_server_mode"
VERSION = 1


def is_neo_server(store):
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name=%s", (SETTING,)
        ).fetchone()
    if row is None:
        raise ValueError("Dungeon server mode is not configured")
    value = row["value"]
    if (
        not isinstance(value, dict)
        or type(value.get("version")) is not int
        or value["version"] != VERSION
        or type(value.get("is_neo_server")) is not bool
        or set(value) != {"version", "is_neo_server"}
    ):
        raise ValueError("Dungeon server mode configuration is invalid")
    return value["is_neo_server"]


def evaluate(store, criterion, *, character=None, queries=None, now_ms=None):
    """Evaluate restricted native predicates against explicit server authority.

    Missing state/achievement snapshots are unknown, never false. The caller
    may supply trusted query producers; client-controlled fields are not used.
    """
    import ast
    import re
    import operator
    from types import SimpleNamespace
    from wakfu_server.combat_local_criteria import parse_local_criterion
    from wakfu_server.combat_inventory_date_conditions import (
        calendar_milliseconds,
        owned_item_quantity,
    )
    from wakfu_server.combat_system_conditions import (
        boolean_system_configuration,
        fresh_system_configuration,
    )

    if not isinstance(criterion, str) or len(criterion) > 32768:
        raise ValueError("Malformed dungeon criterion")
    if not criterion.strip():
        return True
    # Native localized annotations change error metadata, not their predicate.
    annotated = re.sub(
        r'@\("[^"\n]+"\)\s*([^@]+)@', lambda match: "(" + match[1] + ")", criterion
    )
    if "@" in annotated:
        raise ValueError("Malformed dungeon criterion annotation")
    # Native SHARP wraps predicate metadata without rebinding its arguments.
    # Normalize this dungeon annotation before the unchanged combat parser.
    annotated = re.sub(r"#([^#]+)#", lambda match: "(" + match[1] + ")", annotated)
    if "#" in annotated:
        raise ValueError("Malformed dungeon criterion SHARP annotation")
    tree = parse_local_criterion(annotated)
    queries = {} if queries is None else queries
    if not isinstance(queries, dict):
        raise ValueError("Invalid dungeon criterion query authority")
    names = {
        "IsNeoServer",
        "GetBooleanSystemConfiguration",
        "GetRealLevel",
        "GetItemQuantity",
        "HasState",
        "IsAfter",
        "IsBefore",
        "IsAchievementRunning",
        "IsAchievementObjectiveComplete",
        "IsAchievementComplete",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name) or node.func.id not in names
        ):
            raise ValueError("Unsupported dungeon criterion")
    comparisons = {
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
    }

    def boolean(value):
        if type(value) is not bool:
            raise ValueError("Dungeon predicate lacks boolean authority")
        return value

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, str, bool):
            return node.value
        if isinstance(node, ast.BoolOp):
            values = [boolean(visit(value)) for value in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not boolean(visit(node.operand))
        if isinstance(node, ast.Compare):
            left = visit(node.left)
            result = True
            for op, right_node in zip(node.ops, node.comparators):
                right = visit(right_node)
                if (
                    type(left) is not int
                    or type(right) is not int
                    or type(op) not in comparisons
                ):
                    raise ValueError("Unsupported dungeon comparison")
                result = comparisons[type(op)](left, right) and result
                left = right
            return result
        if isinstance(node, ast.Call):
            name, args = node.func.id, tuple(visit(arg) for arg in node.args)
            if name == "IsNeoServer" and not args:
                return is_neo_server(store)
            if name == "GetBooleanSystemConfiguration" and len(args) == 1:
                return boolean_system_configuration(
                    SimpleNamespace(
                        native_system_configuration=fresh_system_configuration()
                    ),
                    args[0],
                )
            if name == "GetRealLevel" and not args:
                level = None if character is None else character.get("level")
                if type(level) is not int or level < 1:
                    raise ValueError("Missing real character level authority")
                return level
            if name == "GetItemQuantity" and args:
                return owned_item_quantity(
                    None if character is None else character.get("inventory_items"),
                    args,
                )
            if name in ("IsAfter", "IsBefore"):
                date = calendar_milliseconds(args)
                current = now_ms
                if current is None:
                    current = int(store.clock() * 1000)
                if type(current) is not int:
                    raise ValueError("Missing current UTC date authority")
                return current > date if name == "IsAfter" else current < date
            if name in (
                "HasState",
                "IsAchievementRunning",
                "IsAchievementObjectiveComplete",
                "IsAchievementComplete",
            ):
                if len(args) != 1 or type(args[0]) is not int or args[0] <= 0:
                    raise ValueError("Invalid dungeon state or achievement predicate")
                query = queries.get(name)
                if not callable(query):
                    raise ValueError("Missing dungeon predicate authority: " + name)
                return boolean(query(args[0]))
            raise ValueError("Unsupported dungeon criterion arguments")
        raise ValueError("Unsupported dungeon criterion syntax")

    return boolean(visit(tree))
