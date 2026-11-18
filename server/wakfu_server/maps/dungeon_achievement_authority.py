"""Trusted independent native achievement flags for access expressions.

Active is a persisted flag with its own acceptance-period policy. Running is
Active and not Complete. Definitions, client previews and completion alone are
never activation authority; absent/malformed snapshots remain unknown.
"""


def queries_from_snapshot(snapshot, *, now_ms=None):
    required = {"running", "completed", "objectives"}
    optional = {"active", "active_periods", "active_unknown"}
    if (
        not isinstance(snapshot, dict)
        or not required <= set(snapshot)
        or set(snapshot) - required - optional
        or ("active_periods" in snapshot or "active_unknown" in snapshot)
        and "active" not in snapshot
    ):
        raise ValueError("Missing or malformed achievement authority")
    for key in required | ({"active"} if "active" in snapshot else set()):
        values = snapshot[key]
        if not isinstance(values, list) or any(
            type(value) is not int or not 0 < value < 2**31 for value in values
        ):
            raise ValueError("Malformed achievement authority identifiers")
    running, completed, objectives = (
        frozenset(snapshot[key]) for key in ("running", "completed", "objectives")
    )
    if running & completed:
        raise ValueError("Achievement cannot be running and completed")
    from wakfu_server.achievements.lifecycle import active_predicate

    active = active_predicate(snapshot, now_ms=now_ms, strict=True)

    return {
        "IsAchievementActive": active,
        "IsAchievementRunning": lambda identifier: identifier not in completed
        and active(identifier),
        "IsAchievementComplete": lambda identifier: identifier in completed,
        "IsAchievementObjectiveComplete": lambda identifier: identifier in objectives,
    }


def queries_from_state(state, *, now_ms=None):
    """Keep independent flags when projecting a trusted mutable engine state."""
    from wakfu_server.achievements.lifecycle import snapshot

    return queries_from_snapshot(snapshot(state), now_ms=now_ms)


def queries(store, character_id):
    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Missing achievement owner")
    with store.connection() as db:
        row = db.execute(
            "SELECT snapshot FROM character_achievement_authority WHERE character_id=%s",
            (character_id,),
        ).fetchone()
    return queries_from_snapshot(
        None if row is None else row["snapshot"],
        now_ms=(
            int(store.clock() * 1000)
            if callable(getattr(store, "clock", None))
            else None
        ),
    )


def evaluate(store, criterion, *, character):
    """Evaluate native criteria with server-owned achievement facts when needed."""
    from wakfu_server import dungeon_criteria

    authority = None
    if any(
        name in criterion
        for name in (
            "IsAchievementActive",
            "IsAchievementRunning",
            "IsAchievementComplete",
            "IsAchievementObjectiveComplete",
        )
    ):
        authority = queries(store, character["id"])
    return dungeon_criteria.evaluate(
        store, criterion, character=character, queries=authority
    )
