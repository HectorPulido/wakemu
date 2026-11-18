"""Source-declared exclusive entry variants, independent of physical access."""


def _positive(value):
    return type(value) is int and value > 0


def alternatives(admission):
    if not isinstance(admission, dict) or not _positive(
        admission.get("continuation_quest_id")
    ):
        raise ValueError("Missing explicit owned story admission")
    if set(admission) == {"quest_id", "objective_id", "continuation_quest_id"}:
        rows = [{key: admission[key] for key in ("quest_id", "objective_id")}]
    elif set(admission) == {"alternatives", "continuation_quest_id"}:
        rows = admission["alternatives"]
    else:
        raise ValueError("Unknown owned story admission shape")
    if (
        not isinstance(rows, list)
        or not rows
        or any(
            not isinstance(row, dict)
            or set(row) != {"quest_id", "objective_id"}
            or not _positive(row["quest_id"])
            or row["objective_id"] is not None
            and not _positive(row["objective_id"])
            for row in rows
        )
        or len({row["quest_id"] for row in rows}) != len(rows)
    ):
        raise ValueError("Owned story entry variants lack unique native objectives")
    return tuple(dict(row) for row in rows)


def quest_ids(admission):
    """All exclusive entry quests plus the actual continuation quest."""
    return {row["quest_id"] for row in alternatives(admission)} | {
        admission["continuation_quest_id"]
    }


def running_variant(admission, state):
    rows = alternatives(admission)
    completed = set(state["completed"])
    running = [
        row
        for row in rows
        if row["quest_id"] in state["running"] and row["quest_id"] not in completed
    ]
    if len(running) > 1:
        raise ValueError("Multiple mutually exclusive entry quests are running")
    return running[0] if running else None


def admitted(admission, state):
    """Optional followups require genuine predecessor and continuation state."""
    return bool(
        {row["quest_id"] for row in alternatives(admission)} & set(state["completed"])
    ) and admission["continuation_quest_id"] in set(state["running"]) | set(
        state["completed"]
    )
