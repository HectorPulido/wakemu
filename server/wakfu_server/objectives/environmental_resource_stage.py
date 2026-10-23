"""Resolve declared physical stages without rewriting original scenario steps."""
from hashlib import sha256
import json


def resolve(db, source_key, scenario_id):
    rows = db.execute(
        "SELECT * FROM environmental_resolved_resource_actions "
        "WHERE source_key=%s AND scenario_id=%s",
        (source_key, scenario_id),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("Environmental resource needs one qualified physical action")
    row = rows[0]
    from wakfu_server.resource_collect import action

    native = action(row["resource_reference"], row["native_step"], row["action_id"])
    encoded = json.dumps(
        native, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    if (
        native != row["original_action"]
        or sha256(encoded).hexdigest() != row["action_sha256"]
    ):
        raise ValueError("Resolved resource stage differs from current original action")
    return row
