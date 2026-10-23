"""Native item USE criteria against the owned outside-combat self context."""
import ast
import operator
from types import SimpleNamespace


def evaluate(text, character, *, native_map_id=None):
    from wakfu_server.combat_local_criteria import parse_local_criterion

    if not isinstance(text, str):
        raise ValueError("Invalid native consumable criterion")
    if not text.strip():
        return True
    states = tuple(character.get("consumable_states", ()))
    comparisons = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
    }

    def self_selector(args):
        if len(args) > 1 or (args and args[0] not in ("caster", "target")):
            raise ValueError("Unsupported consumable actor selector")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, bool, str):
            return node.value
        if isinstance(node, ast.BoolOp):
            values = [visit(value) for value in node.values]
            if any(type(value) is not bool for value in values):
                raise ValueError("Invalid consumable criterion Boolean")
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
                    raise ValueError("Invalid consumable criterion comparison")
                result = comparisons[type(operation)](left, right) and result
                left = right
            return result
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
        ):
            name, args = node.func.id, [visit(value) for value in node.args]
            if name == "__wakemu_native_sharp__" and len(args) == 1:
                return args[0]
            if name in ("HasState", "GetStateLevel") and 1 <= len(args) <= 2:
                identity = args[0]
                if type(identity) is not int or identity <= 0:
                    raise ValueError("Invalid native consumable state identity")
                self_selector(args[1:])
                level = next(
                    (
                        state["level"]
                        for state in states
                        if state["state_id"] == identity
                    ),
                    -1,
                )
                return level >= 0 if name == "HasState" else level
            if name == "GetRealLevel":
                self_selector(args)
                return character["level"]
            if name == "GetLevel" and not args:
                return character.get("effective_level", character["level"])
            if name in ("GetCharacteristic", "GetCharacteristicMax") and args == ["HP"]:
                return character["hp" if name == "GetCharacteristic" else "max_hp"]
            if name == "IsBattleground" and not args:
                from wakfu_server.native_world_context import is_battleground

                from wakfu_server.simple_item_actions import criterion_world_identity

                return is_battleground(
                    criterion_world_identity(character, native_map_id)
                )
            if name == "IsNeoServer" and not args:
                from wakfu_server.combat_system_conditions import (
                    boolean_system_configuration,
                    fresh_system_configuration,
                )

                return boolean_system_configuration(
                    SimpleNamespace(
                        native_system_configuration=fresh_system_configuration()
                    ),
                    "server.group.isneo",
                )
        raise ValueError("Unsupported native consumable criterion")

    value = visit(parse_local_criterion(text))
    if type(value) is not bool:
        raise ValueError("Consumable criterion did not produce a Boolean")
    return value
