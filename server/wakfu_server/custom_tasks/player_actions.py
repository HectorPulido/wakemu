"""Durable browser actions consumed only by the owning World dispatcher."""
import os
from urllib.parse import urlsplit


def launch_url(db, account_id, character_id, generation):
    from wakfu_server.objectives.player_auth import issue_launch

    origin = os.environ.get(
        "WAKFU_OBJECTIVES_PUBLIC_URL", "http://127.0.0.1:18086/player/"
    )
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid objectives player URL")
    return origin + "#token=" + issue_launch(db, account_id, character_id, generation)


def claim(db, identity):
    """Claim once; running transport is never replayed after an uncertain crash."""
    from wakfu_server.objectives.player_auth import validate_identity

    validate_identity(db, identity, lock=True)
    db.execute(
        "UPDATE objectives_player_actions SET status='rejected',"
        "result='{}'::jsonb || jsonb_build_object('error','Action expired before World was ready'),"
        "completed_at=CURRENT_TIMESTAMP WHERE account_id=%s AND character_id=%s "
        "AND generation=%s AND status='pending' AND expires_at<=CURRENT_TIMESTAMP",
        (identity["account_id"], identity["character_id"], identity["generation"]),
    )
    return db.execute(
        "UPDATE objectives_player_actions SET status='running' WHERE id=("
        "SELECT id FROM objectives_player_actions WHERE account_id=%s AND character_id=%s "
        "AND generation=%s AND status='pending' AND expires_at>CURRENT_TIMESTAMP "
        "ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *",
        (identity["account_id"], identity["character_id"], identity["generation"]),
    ).fetchone()


def finish(db, action, result):
    """Receipt only: a stale selected character cannot execute a second action."""
    from psycopg.types.json import Jsonb

    return (
        db.execute(
            "UPDATE objectives_player_actions SET status=%s,result=%s,completed_at=CURRENT_TIMESTAMP "
            "WHERE id=%s AND account_id=%s AND character_id=%s AND generation=%s "
            "AND status='running' RETURNING id",
            (
                "succeeded" if result["success"] else "rejected",
                Jsonb(result),
                action["id"],
                action["account_id"],
                action["character_id"],
                action["generation"],
            ),
        ).fetchone()
        is not None
    )


def lock_running(db, action):
    """Fence transport and its success receipt in the same gameplay transaction."""
    from wakfu_server.objectives.player_auth import validate_identity

    validate_identity(db, action, lock=True)
    row = db.execute(
        "SELECT id FROM objectives_player_actions WHERE id=%s AND account_id=%s "
        "AND character_id=%s AND generation=%s AND status='running' "
        "AND expires_at>CURRENT_TIMESTAMP FOR UPDATE",
        (
            action["id"],
            action["account_id"],
            action["character_id"],
            action["generation"],
        ),
    ).fetchone()
    if row is None:
        raise ValueError("Adventures action expired or is no longer executable.")


def nearby_public_floor(geometry, opponent, *, occupied=()):
    """Choose actual mutually reachable floor beside a server-owned position."""
    from wakfu_server.combat.combat_geometry import prepare_geometry

    if opponent.get("instance_id", 0):
        raise ValueError("PvP meeting requires a public world location.")
    geometry = prepare_geometry(geometry)
    if geometry.map_id != opponent["map_id"]:
        raise ValueError("PvP geometry does not match the opponent's map.")
    source = tuple(opponent[key] for key in ("x", "y", "z"))
    cells = geometry.cells
    edges = geometry.edges
    heights = {}
    for x, y, z in cells:
        heights.setdefault((x, y), set()).add(z)
    blocked = set(occupied) | {source}
    candidates = [
        cell
        for cell in cells
        if cell not in blocked
        and abs(cell[0] - source[0]) + abs(cell[1] - source[1]) == 1
        and len(heights[cell[:2]]) == 1
        and (source, cell) in edges
        and (cell, source) in edges
    ]
    if not candidates:
        raise ValueError("No available native floor beside the PvP opponent.")
    target = min(candidates, key=lambda cell: (abs(cell[2] - source[2]), *cell))
    return dict(
        map_id=opponent["map_id"], instance_id=0, x=target[0], y=target[1], z=target[2]
    )


def charge_travel(db, action, cost):
    """Debit the locked action's account inside the transport transaction."""
    if type(cost) is not int or not 1 <= cost < 2**63:
        raise ValueError("Invalid adventures travel price.")
    lock_running(db, action)
    row = db.execute(
        "UPDATE account_wallets SET kamas=kamas-%s WHERE account_id=%s AND kamas>=%s "
        "RETURNING kamas",
        (cost, action["account_id"], cost),
    ).fetchone()
    if row is None:
        raise ValueError(f"Insufficient kamas. Adventures travel costs {cost:,} kamas.")
    return row["kamas"]
