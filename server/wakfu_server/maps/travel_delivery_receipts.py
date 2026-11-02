"""Retire obsolete delivery hints without replaying durable travel or consumption."""
from psycopg import sql

LOCATION_KEYS = ("map_id", "instance_id", "x", "y", "z")
_TABLES = frozenset(("haven_world_transitions", "item_teleport_receipts"))


def supersede_moved(db, table, receipt, current, *, now):
    """Caller holds the selected lease, current character and receipt row locks.

    The locked character owns its actual location; the old arrival is only a
    presentation hint. Keep the original destination and all consumption facts.
    No clock ordering is inferred from timestamps that can legitimately regress.
    """
    if table not in _TABLES:
        raise ValueError("Unknown travel delivery ledger")
    if (
        receipt["account_id"] != current["account_id"]
        or receipt["character_id"] != current["id"]
    ):
        raise ValueError("Travel delivery receipt belongs to another character")
    if receipt["delivered_at"] is not None or receipt["superseded_at"] is not None:
        return False
    if all(current[key] == receipt["destination"][key] for key in LOCATION_KEYS):
        return False
    db.execute(
        sql.SQL(
            "UPDATE {} SET superseded_at=%s WHERE token=%s "
            "AND delivered_at IS NULL AND superseded_at IS NULL"
        ).format(sql.Identifier(table)),
        (now, receipt["token"]),
    )
    return True


def notify_superseded(account_id, generation, character_id, current):
    """Wake the existing owned scene publisher only after the SQL commit."""
    from wakfu_server.rift_transition_delivery import queue_owned_position_refresh

    queue_owned_position_refresh(
        account_id,
        generation,
        character_id,
        {key: current[key] for key in LOCATION_KEYS},
    )
