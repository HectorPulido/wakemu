"""Trusted achievement predicates for native dungeon access expressions.

The local server owns this ledger. Empty initialized snapshots mean no quest
has started, whereas an absent snapshot remains unknown and fails closed.
Client requests never write achievement facts through this module.
"""


def queries_from_snapshot(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "running",
        "completed",
        "objectives",
    }:
        raise ValueError("Missing or malformed achievement authority")
    for values in snapshot.values():
        if not isinstance(values, list) or any(
            type(value) is not int or value <= 0 for value in values
        ):
            raise ValueError("Malformed achievement authority identifiers")
    running, completed, objectives = (
        frozenset(snapshot[key]) for key in ("running", "completed", "objectives")
    )
    if running & completed:
        raise ValueError("Achievement cannot be running and completed")
    return {
        "IsAchievementRunning": lambda identifier: identifier in running,
        "IsAchievementComplete": lambda identifier: identifier in completed,
        "IsAchievementObjectiveComplete": lambda identifier: identifier in objectives,
    }


def queries(store, character_id):
    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Missing achievement owner")
    with store.connection() as db:
        row = db.execute(
            "SELECT snapshot FROM character_achievement_authority WHERE character_id=%s",
            (character_id,),
        ).fetchone()
    return queries_from_snapshot(None if row is None else row["snapshot"])


def evaluate(store, criterion, *, character):
    """Evaluate native criteria with server-owned achievement facts when needed."""
    from wakfu_server.maps import dungeon_criteria

    authority = None
    if any(
        name in criterion
        for name in (
            "IsAchievementRunning",
            "IsAchievementComplete",
            "IsAchievementObjectiveComplete",
        )
    ):
        authority = queries(store, character["id"])
    return dungeon_criteria.evaluate(
        store, criterion, character=character, queries=authority
    )
