"""Generate entrance-scoped native client mission prerequisite overrides."""
import argparse
import ast
import json
import hashlib
import re
from pathlib import Path
from wakfu_server.combat_local_criteria import parse_local_criterion

WAIVED = {
    "HasState",
    "IsAchievementRunning",
    "IsAchievementComplete",
    "IsAchievementObjectiveComplete",
}


def combine(values, conjunction):
    absorbing, identity = (False, True) if conjunction else (True, False)
    if any(type(value) is bool and value == absorbing for value in values):
        return absorbing
    values = [
        value for value in values if not (type(value) is bool and value == identity)
    ]
    if not values:
        return identity
    if len(values) == 1:
        return values[0]
    return ast.BoolOp(op=ast.And() if conjunction else ast.Or(), values=values)


def negate(value):
    return (
        not value if type(value) is bool else ast.UnaryOp(op=ast.Not(), operand=value)
    )


def projected_criterion(criterion):
    """Return not(definitely-false), accepting unknown waived mission gates."""
    annotated = re.sub(
        r'@\("[^"\n]+"\)\s*([^@]+)@', lambda m: "(" + m[1] + ")", criterion
    )
    annotated = re.sub(r"#([^#]+)#", lambda m: "(" + m[1] + ")", annotated)
    tree = parse_local_criterion(annotated)

    def bounds(node):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in WAIVED
        ):
            if (
                len(node.args) != 1
                or not isinstance(node.args[0], ast.Constant)
                or type(node.args[0].value) is not int
                or node.args[0].value <= 0
            ):
                raise ValueError("Malformed mission prerequisite")
            return False, False
        if isinstance(node, ast.BoolOp):
            pairs = [bounds(value) for value in node.values]
            is_and = isinstance(node.op, ast.And)
            return combine([p[0] for p in pairs], is_and), combine(
                [p[1] for p in pairs], not is_and
            )
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            true, false = bounds(node.operand)
            return false, true
        if any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id in WAIVED
            for child in ast.walk(node)
        ):
            raise ValueError("Mission prerequisite used as a non-boolean operand")
        return node, negate(node)

    _, false = bounds(tree)
    result = negate(false)
    if type(result) is bool:
        return (
            "(IsNeoServer() or not IsNeoServer())"
            if result
            else "(IsNeoServer() and not IsNeoServer())"
        )

    def render(node):
        if isinstance(node, ast.Constant):
            if type(node.value) is bool:
                return (
                    "(IsNeoServer() or not IsNeoServer())"
                    if node.value
                    else "(IsNeoServer() and not IsNeoServer())"
                )
            return (
                json.dumps(node.value)
                if isinstance(node.value, str)
                else str(node.value)
            )
        if isinstance(node, ast.Call):
            return (
                node.func.id + "(" + ", ".join(render(arg) for arg in node.args) + ")"
            )
        if isinstance(node, ast.BoolOp):
            return (
                "("
                + (" and " if isinstance(node.op, ast.And) else " or ").join(
                    render(v) for v in node.values
                )
                + ")"
            )
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return "(not " + render(node.operand) + ")"
        if isinstance(node, ast.Compare):
            ops = {
                ast.Eq: "=",
                ast.NotEq: "!=",
                ast.Gt: ">",
                ast.GtE: ">=",
                ast.Lt: "<",
                ast.LtE: "<=",
            }
            return (
                "("
                + render(node.left)
                + "".join(
                    " " + ops[type(op)] + " " + render(value)
                    for op, value in zip(node.ops, node.comparators)
                )
                + ")"
            )
        raise ValueError("Unsupported native projection syntax")

    return render(result)


def build(inventory):
    rows = {}
    for record in inventory["records"]:
        for route in record["native_entry_routes"]:
            criterion = route["criterion"]
            if not any(name in criterion for name in WAIVED):
                continue
            identity = route["destination_id"]
            effective = projected_criterion(criterion)
            if identity in rows and rows[identity] != effective:
                raise ValueError("Conflicting native destination identity")
            rows[identity] = effective
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory", type=Path, default=Path("docs/reports/dungeons/inventory.json")
    )
    parser.add_argument(
        "--client-jar", type=Path, default=Path("client/lib/wakfu-client.jar")
    )
    parser.add_argument(
        "--source-version",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "client-tools/runtime/dungeon-entry-source-version.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("client-tools/runtime/dungeon-entry-overrides.properties"),
    )
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text())
    pinned = json.loads(args.source_version.read_text())
    digest = hashlib.sha256(args.client_jar.read_bytes()).hexdigest()
    if (
        type(pinned.get("version")) is not int
        or pinned.get("version") != 1
        or pinned.get("native_client_sha256") != digest
        or pinned.get("native_catalog_release") != inventory.get("live_catalog_release")
    ):
        raise ValueError(
            "Native entrance inventory/client version mismatch; re-extract and review both before updating the source version pin"
        )
    rows = build(inventory)
    # java.util.Properties requires escaped backslashes; expressions have no newlines.
    args.output.write_text(
        "native_sha256="
        + digest
        + "\n# Generated from native entrance routes; never internal doors.\n"
        + "".join(
            f"{identity}={expression.replace(chr(92), chr(92) * 2)}\n"
            for identity, expression in sorted(rows.items())
        )
    )
    print(f"Generated {len(rows)} scoped native entry overrides: {args.output}")


if __name__ == "__main__":
    main()
