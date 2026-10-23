"""Shared environmental lifecycle and objective rules, independent of transport.

Catalogue membership never authorizes an event by itself. A runnable profile
must bind its scope, timing, objectives and reward authority explicitly.
"""
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass


FAMILIES = frozenset(
    (
        "monster_defeat",
        "group_defeat",
        "resource_collect",
        "resource_plant",
        "monster_destroy",
    )
)
_FACT_FAMILIES = {
    "monster_defeated": "monster_defeat",
    "group_defeated": "group_defeat",
    "resource_collected": "resource_collect",
    "resource_planted": "resource_plant",
    "monster_destroyed": "monster_destroy",
}


def integer(value, name, *, minimum=0):
    if type(value) is not int or value < minimum or value >= 2**63:
        raise ValueError("Invalid environmental " + name)
    return value


def validate_profile(profile, objectives):
    """Reject incomplete runnable policy, independently of catalogue inventory."""
    if profile.get("family") not in FAMILIES:
        raise ValueError("Unsupported environmental profile family")
    if profile.get("mode") not in ("solo", "collaborative", "race", "competitive"):
        raise ValueError("Unqualified environmental contribution mode")
    if profile["mode"] in ("race", "competitive"):
        validate_evaluation(profile["mode"], profile.get("evaluation"))
    for name in ("version", "map_id", "region_id", "duration_ms"):
        integer(profile.get(name), name, minimum=1)
    for name in ("profile_key", "authority", "catalog_revision"):
        if type(profile.get(name)) is not str or not profile[name].strip():
            raise ValueError("Missing environmental " + name)
    digest = profile.get("source_sha256")
    if (
        type(digest) is not str
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        raise ValueError("Missing environmental source digest")
    integer(profile.get("level_min"), "minimum level", minimum=1)
    integer(profile.get("level_max"), "maximum level", minimum=1)
    if profile["level_min"] > profile["level_max"]:
        raise ValueError("Invalid environmental level interval")
    cycle_window(
        profile["anchor_ms"],
        duration_ms=profile["duration_ms"],
        anchor_ms=profile["anchor_ms"],
        recurrence_period_ms=profile.get("recurrence_period_ms"),
    )
    integer(profile.get("proposal_ms", 0), "proposal duration")
    rows = tuple(objectives)
    keys = set()
    if not rows:
        raise ValueError("Environmental profile requires objectives")
    for row in rows:
        key = row.get("objective_key")
        if type(key) is not str or not key or key in keys:
            raise ValueError("Invalid environmental objective identity")
        keys.add(key)
        if row.get("family") not in FAMILIES:
            raise ValueError("Unsupported environmental objective family")
        if row["family"] != profile["family"]:
            raise ValueError("Environmental objective is outside its family policy")
        integer(row.get("required_quantity"), "required quantity", minimum=1)
        if row.get("unit", "interaction") not in ("interaction", "quantity"):
            raise ValueError("Unsupported environmental objective unit")
        for field in ("target_reference", "action_id"):
            if row.get(field) is not None:
                integer(row[field], field, minimum=1)
        if row.get("resource_step") is not None:
            integer(row["resource_step"], "resource step")
    return rows


def cycle_window(now_ms, *, duration_ms, anchor_ms, recurrence_period_ms=None):
    """Return an anchored half-open admission window, or None between cycles."""
    integer(now_ms, "clock")
    integer(anchor_ms, "anchor")
    integer(duration_ms, "duration", minimum=1)
    if recurrence_period_ms is not None:
        integer(recurrence_period_ms, "period", minimum=1)
        if duration_ms > recurrence_period_ms:
            raise ValueError("Environmental duration exceeds its recurrence")
    if now_ms < anchor_ms:
        return None
    cycle = (
        0
        if recurrence_period_ms is None
        else (now_ms - anchor_ms) // recurrence_period_ms
    )
    starts = anchor_ms + cycle * (recurrence_period_ms or 0)
    deadline = starts + duration_ms
    if deadline >= 2**63:
        raise ValueError("Environmental deadline overflow")
    return None if now_ms >= deadline else (cycle, starts, deadline)


def remaining_ms(deadline_ms, now_ms):
    integer(deadline_ms, "deadline")
    integer(now_ms, "clock")
    return max(0, deadline_ms - now_ms)


def admission_window(
    now_ms, *, duration_ms, anchor_ms, recurrence_period_ms=None, proposal_ms=0
):
    """Choose the live period or its explicit pre-start proposal window."""
    integer(proposal_ms, "proposal duration")
    running = cycle_window(
        now_ms,
        duration_ms=duration_ms,
        anchor_ms=anchor_ms,
        recurrence_period_ms=recurrence_period_ms,
    )
    if running is not None:
        return (*running, "active")
    if proposal_ms == 0:
        return None
    if now_ms < anchor_ms:
        cycle = 0
    elif recurrence_period_ms is None:
        return None
    else:
        cycle = (now_ms - anchor_ms) // recurrence_period_ms + 1
    starts = anchor_ms + cycle * (recurrence_period_ms or 0)
    deadline = starts + duration_ms
    integer(deadline, "deadline", minimum=1)
    return (
        (cycle, starts, deadline, "proposed")
        if now_ms >= starts - proposal_ms
        else None
    )


def fact_values(fact):
    if is_dataclass(fact) and not isinstance(fact, type):
        return asdict(fact)
    if not isinstance(fact, Mapping):
        raise ValueError("Environmental contribution requires a typed fact")
    return dict(fact)


def objective_increment(objective, fact, *, membership):
    """Match a committed entity against one frozen objective and its roster.

    Interaction objectives count once regardless of harvest item yield; an
    explicitly qualified quantity objective uses its actual settled quantity.
    A group fact is separate from a member defeat; receipts deduplicate both.
    Membership is an exact persisted entity identity, never just a breed match.
    """
    values = fact_values(fact)
    family = objective.get("family")
    if family not in FAMILIES:
        raise ValueError("Unsupported environmental objective family")
    integer(objective.get("required_quantity"), "required quantity", minimum=1)
    if _FACT_FAMILIES.get(values.get("kind")) != family:
        return 0
    if membership is None:
        return 0
    for field in ("entity_kind", "entity_id", "reference"):
        if membership.get(field) != values.get(field):
            return 0
    target = objective.get("target_reference")
    if target is not None and target != values.get("reference"):
        return 0
    action = objective.get("action_id")
    if action is not None and action != values.get("action_id"):
        return 0
    stage = objective.get("resource_step")
    stage_field = "after_step" if family == "resource_plant" else "before_step"
    if stage is not None and stage != values.get(stage_field):
        return 0
    unit = objective.get("unit", "interaction")
    if unit == "interaction":
        return 1
    if unit == "quantity":
        return integer(values.get("quantity"), "settled resource quantity")
    raise ValueError("Unsupported environmental objective unit")


def advance_progress(current, increment, required):
    integer(current, "progress")
    integer(increment, "increment")
    integer(required, "required quantity", minimum=1)
    return min(required, current + increment)


def complete(objectives, progress):
    """An empty objective list cannot produce an entitlement."""
    rows = tuple(objectives)
    return bool(rows) and all(
        integer(progress.get(row["objective_key"], 0), "progress")
        >= integer(row["required_quantity"], "required quantity", minimum=1)
        for row in rows
    )


def validate_evaluation(mode, evaluation):
    if not isinstance(evaluation, Mapping):
        raise ValueError("Missing declared environmental ranking policy")
    expected = "first_completion" if mode == "race" else "score_at_deadline"
    if evaluation.get("evaluator") != expected:
        raise ValueError("Environmental ranking evaluator differs from mode")
    integer(evaluation.get("winner_count"), "winner count", minimum=1)
    if evaluation["winner_count"] > 32767:
        raise ValueError("Environmental ranking exceeds native display")
    ties = ("commit_order",) if mode == "race" else ("share_boundary", "character_id")
    if evaluation.get("tie_policy") not in ties or not evaluation.get(
        "source_authority"
    ):
        raise ValueError("Missing qualified environmental tie authority")
    return evaluation


def competitive_order(rows, evaluation):
    """Rank complete eligible participants under an explicitly declared policy."""
    validate_evaluation("competitive", evaluation)
    ordered = sorted(
        rows,
        key=lambda row: (
            -integer(row["score"], "score"),
            integer(row["character_id"], "ranked character", minimum=1),
        ),
    )
    if len({row["character_id"] for row in ordered}) != len(ordered):
        raise ValueError("Repeated environmental ranked character")
    winners = evaluation["winner_count"]
    share = evaluation["tie_policy"] == "share_boundary"
    boundary = ordered[min(winners, len(ordered)) - 1]["score"] if ordered else None
    result = []
    rank, last = 0, None
    for position, row in enumerate(ordered, 1):
        if not share or row["score"] != last:
            rank = position
        last = row["score"]
        result.append(
            dict(
                row,
                position=position,
                display_rank=rank,
                rewarded=position <= winners or (share and row["score"] == boundary),
            )
        )
    return tuple(result)
