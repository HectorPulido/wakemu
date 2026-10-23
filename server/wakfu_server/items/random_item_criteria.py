"""Restricted native random-box entry criteria from the owned world context."""
import ast
import operator


def evaluate(text, character, *, native_map_id, is_neo_server):
    from wakfu_server.combat_local_criteria import parse_local_criterion

    if not isinstance(text, str) or type(is_neo_server) is not bool:
        raise ValueError("Invalid native random item criterion context")
    if not text.strip():
        return True
    from wakfu_server.simple_item_actions import criterion_world_identity

    native_map_id = criterion_world_identity(character, native_map_id)
    states = character.get("consumable_states", ())
    comparisons = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
    }

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, bool):
            return node.value
        if isinstance(node, ast.BoolOp):
            values = [visit(value) for value in node.values]
            if any(type(value) is not bool for value in values):
                raise ValueError("Invalid native random criterion Boolean")
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = visit(node.operand)
            if type(value) is bool:
                return not value
        if isinstance(node, ast.Compare):
            left = visit(node.left)
            result = True
            for operation, right_node in zip(node.ops, node.comparators):
                right = visit(right_node)
                if (
                    type(left) is not int
                    or type(right) is not int
                    or type(operation) not in comparisons
                ):
                    raise ValueError("Invalid native random criterion comparison")
                result = comparisons[type(operation)](left, right) and result
                left = right
            return result
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
        ):
            name, args = node.func.id, [visit(arg) for arg in node.args]
            if name == "GetInstanceId" and not args:
                return native_map_id
            if name == "IsNeoServer" and not args:
                return is_neo_server
            if (
                name == "GetStateLevel"
                and len(args) == 1
                and type(args[0]) is int
                and args[0] > 0
            ):
                # This server's persisted world consumable state registry is
                # authoritative; never synthesize Rift state6836 from a level,
                # completed wave count or a historical combat receipt.
                return next(
                    (row["level"] for row in states if row["state_id"] == args[0]), -1
                )
        raise ValueError("Unsupported native random item criterion")

    result = visit(parse_local_criterion(text))
    if type(result) is not bool:
        raise ValueError("Native random criterion did not return a Boolean")
    return result
