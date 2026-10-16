"""PostgreSQL arena cap, read afresh when a fight is created."""


def size_range(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='combat_arena_size_range'"
    ).fetchone()
    value = None if row is None else row["value"]
    if (
        not isinstance(value, dict)
        or set(value) != {"minimum", "maximum"}
        or any(type(value[key]) is not int for key in value)
        or not 7 <= value["minimum"] <= value["maximum"] <= 50
    ):
        raise ValueError("Invalid PostgreSQL combat arena size range")
    return value["minimum"], value["maximum"]


def cell_budget(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='combat_arena_cell_budget'"
    ).fetchone()
    value = None if row is None else row["value"]
    # Preserve the native 30 x 30 duel minimum and existing wire-tested ceiling.
    if type(value) is not int or not 900 <= value <= 2500:
        raise ValueError("Invalid PostgreSQL combat arena cell budget")
    return value
