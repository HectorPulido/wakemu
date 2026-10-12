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


SETTING = "dungeon_entry_client_overrides"


def validate_setting(value, client_sha256):
    """Validate reviewed DB identity and content before emitting any resource."""
    keys = {
        "version",
        "native_client_sha256",
        "source_catalog_revision",
        "projection_sha256",
        "entrances",
    }
    if (
        not isinstance(value, dict)
        or set(value) != keys
        or type(value["version"]) is not int
        or value["version"] != 1
    ):
        raise ValueError("Missing or malformed native entrance setting")
    for name in (
        "native_client_sha256",
        "source_catalog_revision",
        "projection_sha256",
    ):
        if not isinstance(value[name], str) or not re.fullmatch(
            r"[0-9a-f]{64}", value[name]
        ):
            raise ValueError("Malformed native entrance hash identity")
    if value["native_client_sha256"] != client_sha256:
        raise ValueError("Native entrance/client version mismatch")
    entrances = value["entrances"]
    if not isinstance(entrances, list) or not entrances:
        raise ValueError("Missing reviewed native entrances")
    rows = {}
    for row in entrances:
        if not isinstance(row, dict) or set(row) != {"destination_id", "criterion"}:
            raise ValueError("Malformed native entrance row")
        identity, expression = row["destination_id"], row["criterion"]
        if type(identity) is not int or not 0 < identity < 2**31 or identity in rows:
            raise ValueError("Invalid or duplicate native entrance identity")
        if (
            not isinstance(expression, str)
            or not expression
            or len(expression) > 32768
            or any(c in expression for c in "\r\n\x00")
        ):
            raise ValueError("Malformed native entrance expression")
        parse_local_criterion(expression)
        rows[identity] = expression
    digest = hashlib.sha256(
        json.dumps(entrances, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if digest != value["projection_sha256"]:
        raise ValueError("Native entrance projection hash mismatch")
    return rows


def load_database_rows(db, client_sha256):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    value = None if row is None else row["value"]
    rows = validate_setting(value, client_sha256)
    source = db.execute(
        "SELECT complete FROM native_catalog_releases WHERE revision=%s",
        (value["source_catalog_revision"],),
    ).fetchone()
    if source is None or source["complete"] is not True:
        raise ValueError(
            "Reviewed native entrance source catalog is absent or incomplete"
        )
    return rows


def render_properties(rows, digest):
    return (
        "native_sha256="
        + digest
        + "\n# Generated from native entrance routes; never internal doors.\n"
        + "".join(
            f"{identity}={expression.replace(chr(92), chr(92)*2)}\n"
            for identity, expression in sorted(rows.items())
        )
    )


def read_local_database_rows(client_sha256, *, run=None):
    """DB-only local transport when the launcher's Python lacks psycopg."""
    import subprocess

    run = subprocess.run if run is None else run
    query = (
        "SELECT jsonb_build_object('value',s.value,'complete',r.complete) "
        "FROM settings s LEFT JOIN native_catalog_releases r "
        "ON r.revision=s.value->>'source_catalog_revision' "
        "WHERE s.name='dungeon_entry_client_overrides'"
    )
    result = run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-X",
            "-A",
            "-t",
            "-U",
            "wakemu",
            "-d",
            "wakemu_runtime",
            "-c",
            query,
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise ValueError("PostgreSQL entrance export query failed")
    try:
        envelope = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise ValueError(
            "PostgreSQL entrance setting is missing or malformed"
        ) from None
    if not isinstance(envelope, dict) or set(envelope) != {"value", "complete"}:
        raise ValueError("Malformed PostgreSQL entrance export")
    rows = validate_setting(envelope["value"], client_sha256)
    if envelope["complete"] is not True:
        raise ValueError(
            "Reviewed native entrance source catalog is absent or incomplete"
        )
    return rows


def main():
    import importlib.util
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client-jar", type=Path, default=Path("client/lib/wakfu-client.jar")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("client-tools/runtime/dungeon-entry-overrides.properties"),
    )
    args = parser.parse_args()
    digest = hashlib.sha256(args.client_jar.read_bytes()).hexdigest()
    if importlib.util.find_spec("psycopg") is None:
        if os.environ.get("WAKFU_DATABASE_URL") or os.environ.get(
            "WAKFU_DATABASE_PASSWORD_FILE"
        ):
            raise ValueError(
                "Configured PostgreSQL connection requires psycopg; refusing a different local database"
            )
        rows = read_local_database_rows(digest)
    else:
        import psycopg
        from psycopg.rows import dict_row

        # Match compose.yaml's localhost publication; deployments may override both.
        conninfo = os.environ.get(
            "WAKFU_DATABASE_URL",
            "host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu",
        )
        password_file = Path(
            os.environ.get(
                "WAKFU_DATABASE_PASSWORD_FILE",
                str(
                    Path(__file__).resolve().parents[2]
                    / ".runtime/local/secrets/postgres-password"
                ),
            )
        )
        password = password_file.read_text().strip()
        if not password:
            raise ValueError("Empty PostgreSQL password file")
        with psycopg.connect(
            conninfo, password=password, row_factory=dict_row, connect_timeout=5
        ) as db:
            db.execute("SET TRANSACTION READ ONLY")
            rows = load_database_rows(db, digest)
    args.output.write_text(render_properties(rows, digest))
    print(f"Generated {len(rows)} scoped native entry overrides: {args.output}")


if __name__ == "__main__":
    main()
