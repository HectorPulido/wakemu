"""One opt-in regional environmental event, shared before participant eligibility.

Wakemu round-robin cadence starts a fresh declared window only when occupied.
It does not reinterpret immutable profile anchors as an original server clock.
"""
from . import environmental_presence as presence
from .environmental_runtime import integer


def _scope(location):
    map_id = integer(location["map_id"], "schedule map", minimum=1)
    instance_id = integer(location["instance_id"], "schedule instance")
    region_id = location.get("region_id")
    if region_id is None:
        return None
    return map_id, instance_id, integer(region_id, "schedule region", minimum=1)


def scheduled_scope(db, location):
    """A sealed policy reserves its scope even before the first selected slot.

    This prevents disabled scheduling from silently admitting legacy profiles.
    Empty or unknown-region maps perform no scheduling SQL.
    """
    scope = _scope(location)
    if scope is None or presence.capture(scope[0], scope[1]) is None:
        return False
    from . import environmental_storage as storage

    storage._transaction(db)
    return (
        db.execute(
            "SELECT 1 WHERE EXISTS(SELECT 1 FROM environmental_regional_schedule_policies "
            "WHERE map_id=%s AND region_id=%s AND sealed) "
            "OR EXISTS(SELECT 1 FROM environmental_regional_schedule_slots "
            "WHERE map_id=%s AND world_instance_id=%s AND region_id=%s)",
            (scope[0], scope[2], *scope),
        ).fetchone()
        is not None
    )


def _validate_policy(policy, scope):
    if (
        policy is None
        or not policy["sealed"]
        or (policy["map_id"], policy["region_id"]) != (scope[0], scope[2])
        or policy["selection_policy"] != "wakemu_round_robin"
        or policy["cadence_policy"] != "occupied_sequential_windows"
    ):
        raise ValueError("Invalid frozen environmental regional schedule")
    integer(policy["intermission_ms"], "schedule intermission")


def _previous(db, slot, scope, now_ms):
    policy = db.execute(
        "SELECT * FROM environmental_regional_schedule_policies "
        "WHERE policy_key=%s AND version=%s FOR SHARE",
        (slot["policy_key"], slot["version"]),
    ).fetchone()
    _validate_policy(policy, scope)
    event = db.execute(
        "SELECT e.* FROM environmental_event_instances e "
        "JOIN environmental_regional_schedule_candidates c ON "
        "(c.profile_key,c.profile_version)=(e.profile_key,e.version) "
        "WHERE e.instance_id=%s AND c.policy_key=%s AND c.version=%s AND c.ordinal=%s "
        "FOR UPDATE OF e",
        (
            slot["event_instance_id"],
            slot["policy_key"],
            slot["version"],
            slot["candidate_ordinal"],
        ),
    ).fetchone()
    if (
        event is None
        or (event["map_id"], event["world_instance_id"], event["region_id"]) != scope
        or slot["next_selection_at_ms"]
        != event["deadline_ms"] + policy["intermission_ms"]
    ):
        raise ValueError("Environmental regional slot differs from its frozen event")
    if event["state"] in ("completed", "cancelled"):
        terminal_at = integer(event["terminal_at_ms"], "schedule global terminal clock")
        if terminal_at > now_ms:
            raise ValueError("Environmental terminal outcome is ahead of its clock")
        if (
            db.execute(
                "SELECT 1 FROM environmental_cleanup_outbox WHERE instance_id=%s "
                "AND completed_at_ms IS NULL LIMIT 1",
                (event["instance_id"],),
            ).fetchone()
            is not None
        ):
            return event, False
        # Global settlement releases the regional slot. Personal solo/race
        # completion leaves the shared event active and never takes this path.
        return None, now_ms >= terminal_at + policy["intermission_ms"]
    if now_ms < event["deadline_ms"]:
        return event, False
    if event["state"] in ("proposed", "active"):
        raise ValueError(
            "Scheduled expiry requires shared lifecycle settlement before rotation"
        )
    return None, now_ms >= slot["next_selection_at_ms"]


def select_event(db, *, location, now_ms):
    """Return the exact selected event, or None during intermission/no candidates.

    Call after shared lifecycle expiry. No enrollment, claims, cleanup or
    participant-level selection occurs here. Active events remain pinned until
    deadline, including personal completion and policy version/pointer changes.
    Globally completed/cancelled events rotate after durable cleanup and their
    configured intermission, without waiting for the former activity deadline.
    """
    scope = _scope(location)
    if scope is None:
        return None
    occupied = presence.capture(scope[0], scope[1])
    if occupied is None:
        return None
    integer(now_ms, "schedule clock")
    from . import environmental_storage as storage

    storage._transaction(db)
    storage._scope_lock(db, scope[0], scope[1])
    if not presence.current(occupied, scope[0], scope[1]):
        return None
    slot = db.execute(
        "SELECT * FROM environmental_regional_schedule_slots "
        "WHERE map_id=%s AND world_instance_id=%s AND region_id=%s FOR UPDATE",
        scope,
    ).fetchone()
    if slot is not None:
        event, rotate = _previous(db, slot, scope, now_ms)
        if event is not None or not rotate:
            return event
    policy = db.execute(
        "SELECT * FROM environmental_regional_schedule_policies "
        "WHERE map_id=%s AND region_id=%s AND enabled AND sealed FOR SHARE",
        (scope[0], scope[2]),
    ).fetchone()
    if policy is None:
        return None
    _validate_policy(policy, scope)
    candidates = db.execute(
        "SELECT r.*,c.ordinal AS schedule_ordinal FROM environmental_regional_schedule_candidates c "
        "JOIN environmental_runtime_profiles r ON "
        "(r.profile_key,r.version)=(c.profile_key,c.profile_version) "
        "WHERE c.policy_key=%s AND c.version=%s AND r.enabled AND r.sealed "
        "AND r.map_id=%s AND r.region_id=%s "
        "AND EXISTS(SELECT 1 FROM environmental_profile_publication n WHERE "
        "(n.profile_key,n.version)=(r.profile_key,r.version)) "
        "ORDER BY c.ordinal FOR SHARE OF r",
        (policy["policy_key"], policy["version"], scope[0], scope[2]),
    ).fetchall()
    if not candidates:
        return None
    same_policy = slot is not None and (slot["policy_key"], slot["version"]) == (
        policy["policy_key"],
        policy["version"],
    )
    after = slot["candidate_ordinal"] if same_policy else -1
    from .environmental_location_criteria import profile_eligible

    ordered = [row for row in candidates if row["schedule_ordinal"] > after] + [
        row for row in candidates if row["schedule_ordinal"] <= after
    ]
    profile = next(
        (
            row
            for row in ordered
            if profile_eligible(db, row, world_instance_id=scope[1])
        ),
        None,
    )
    if profile is None:
        return None
    storage._objectives(db, profile)
    starts = now_ms + integer(profile.get("proposal_ms", 0), "schedule proposal")
    deadline = starts + integer(profile["duration_ms"], "schedule duration", minimum=1)
    next_selection = deadline + policy["intermission_ms"]
    integer(next_selection, "schedule next selection")
    cycle = db.execute(
        "SELECT COALESCE(MAX(cycle_key),-1)+1 AS next_cycle FROM environmental_event_instances "
        "WHERE profile_key=%s AND version=%s AND map_id=%s AND world_instance_id=%s",
        (profile["profile_key"], profile["version"], scope[0], scope[1]),
    ).fetchone()["next_cycle"]
    integer(cycle, "schedule profile cycle")
    if not presence.current(occupied, scope[0], scope[1]):
        return None
    event = db.execute(
        "INSERT INTO environmental_event_instances "
        "(profile_key,version,map_id,world_instance_id,region_id,cycle_key,started_at_ms,deadline_ms,state) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (
            profile["profile_key"],
            profile["version"],
            *scope,
            cycle,
            starts,
            deadline,
            "proposed" if starts > now_ms else "active",
        ),
    ).fetchone()
    db.execute(
        "INSERT INTO environmental_regional_schedule_slots "
        "(map_id,world_instance_id,region_id,policy_key,version,candidate_ordinal,event_instance_id,next_selection_at_ms) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT(map_id,world_instance_id,region_id) DO UPDATE SET "
        "policy_key=EXCLUDED.policy_key,version=EXCLUDED.version,candidate_ordinal=EXCLUDED.candidate_ordinal,"
        "event_instance_id=EXCLUDED.event_instance_id,next_selection_at_ms=EXCLUDED.next_selection_at_ms",
        (
            *scope,
            policy["policy_key"],
            policy["version"],
            profile["schedule_ordinal"],
            event["instance_id"],
            next_selection,
        ),
    )
    return event
