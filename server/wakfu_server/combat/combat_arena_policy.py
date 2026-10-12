"""PostgreSQL arena cap, read afresh when a fight is created."""


def cell_budget(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='combat_arena_cell_budget'"
    ).fetchone()
    value = None if row is None else row["value"]
    # Preserve the native 30 x 30 duel minimum and existing wire-tested ceiling.
    if type(value) is not int or not 900 <= value <= 2500:
        raise ValueError("Invalid PostgreSQL combat arena cell budget")
    return value
