"""Independent native active flags and authenticated acceptance-period clocks.

Completion never deactivates a record. Explicit removal/reset and native period
expiry do. Journal previews and mere presence in a definition catalog are not
activation evidence. Legacy completion recovery is restricted to nonperiodic
native definitions with an actual persisted completion date.
"""

from copy import deepcopy
import time

from .native_active_period import active_for_period

EXTRA_FIELDS = frozenset(("active", "active_periods", "active_unknown"))


def validate(state):
    active = state.get("active")
    if active is not None and (
        not isinstance(active, list)
        or any(type(value) is not int or not 0 < value < 2**31 for value in active)
        or len(set(active)) != len(active)
    ):
        raise ValueError("Invalid independent achievement active flags")
    periods = state.get("active_periods", {})
    unknown = state.get("active_unknown", [])
    if (
        not isinstance(unknown, list)
        or any(type(value) is not int or not 0 < value < 2**31 for value in unknown)
        or len(set(unknown)) != len(unknown)
        or not set(unknown) <= set(state["completed"])
        or set(unknown) & set(active or ())
    ):
        raise ValueError("Invalid unknown achievement active history")
    if not isinstance(periods, dict):
        raise ValueError("Invalid achievement active periods")
    for key, proof in periods.items():
        if (
            not isinstance(key, str)
            or not key.isascii()
            or not key.isdigit()
            or not 0 < int(key) < 2**31
            or active is None
            or int(key) not in active
            or not isinstance(proof, dict)
            or set(proof) != {"anchor_ms", "period_seconds", "accepted_at_ms"}
            or type(proof["anchor_ms"]) is not int
            or proof["anchor_ms"] <= 0
            or type(proof["period_seconds"]) is not int
            or proof["period_seconds"] <= 0
            or proof["accepted_at_ms"] is not None
            and (
                type(proof["accepted_at_ms"]) is not int or proof["accepted_at_ms"] < 0
            )
        ):
            raise ValueError("Invalid owned achievement period proof")


def active_predicate(state, *, now_ms=None, strict=False):
    """Freeze one request projection; journal publication stays linear in size."""
    validate(state)
    flags = frozenset(state.get("active", state["running"]))
    completed = frozenset(state["completed"])
    unknown = frozenset(state.get("active_unknown", ()))
    independent = "active" in state
    periods = deepcopy(state.get("active_periods", {}))
    if now_ms is None:
        now_ms = time.time_ns() // 1000000

    def active(identity):
        if identity in unknown:
            if strict:
                raise ValueError("Missing independent achievement active authority")
            return False
        if identity not in flags:
            if strict and not independent and identity in completed:
                raise ValueError("Missing independent achievement active authority")
            return False
        proof = periods.get(str(identity))
        if proof is None:
            return True
        if proof["accepted_at_ms"] is None and strict:
            raise ValueError("Missing owned achievement acceptance clock")
        return active_for_period(
            dict(cjT=proof["anchor_ms"], cjU=proof["period_seconds"]),
            active=True,
            accepted_at_ms=proof["accepted_at_ms"],
            now_ms=now_ms,
        )

    return active


def active_status(state, identity, *, now_ms=None, strict=False):
    """Evaluate one independent flag; unknown anchored clocks cannot authorize."""
    return active_predicate(state, now_ms=now_ms, strict=strict)(identity)


def active_ids(state, *, now_ms=None):
    """Effective flags for native publication; ambiguous clocks stay unasserted."""
    active = active_predicate(state, now_ms=now_ms)
    return frozenset(
        identity
        for identity in state.get("active", state["running"])
        if active(identity)
    )


def snapshot(state):
    """Preserve independent flags instead of projecting them back into Running."""
    result = {
        key: deepcopy(state[key]) for key in ("running", "completed", "objectives")
    }
    if "active" in state:
        # A trusted planner may have just accepted a new quest in this same
        # transaction. Its running insertion is an activation, not a preview.
        result["active"] = sorted(set(state["active"]) | set(state["running"]))
        result["active_periods"] = deepcopy(state.get("active_periods", {}))
        result["active_unknown"] = list(state.get("active_unknown", ()))
    return result


def retain_activation(state):
    """Capture an actually running record before a pure completion removes it."""
    state["active"] = sorted(set(state.get("active", ())) | set(state["running"]))
    state.setdefault("active_periods", {})
    state["active_unknown"] = sorted(
        set(state.get("active_unknown", ())) - set(state["running"])
    )


def reset(state, identity):
    if "active" in state:
        state["active"] = [value for value in state["active"] if value != identity]
    state.get("active_periods", {}).pop(str(identity), None)
    state["running"] = [value for value in state["running"] if value != identity]
    if "active_unknown" in state:
        state["active_unknown"] = [
            value for value in state["active_unknown"] if value != identity
        ]


def _native(db, identities):
    if not identities:
        return {}
    rows = db.execute(
        "SELECT definition_id,data->'native' AS native FROM native_quest_metadata_definitions "
        "WHERE revision=(SELECT revision FROM native_quest_metadata_releases "
        "ORDER BY imported_at DESC LIMIT 1) AND definition_id=ANY(%s)",
        (sorted(identities),),
    ).fetchall()
    return {row["definition_id"]: row["native"] for row in rows}


def _acceptance_clocks(db, character_id, identities):
    if not identities:
        return {}
    rows = db.execute(
        "SELECT definition_id,max(accepted_at_ms) AS accepted_at_ms FROM ("
        "SELECT definition_id,accepted_at_ms FROM character_recurring_mission_cycles "
        "WHERE character_id=%s AND definition_id=ANY(%s) UNION ALL "
        "SELECT definition_id,accepted_at_ms FROM recurring_hunter_acceptances "
        "WHERE character_id=%s AND definition_id=ANY(%s) AND expired_at_ms IS NULL UNION ALL "
        "SELECT definition_id,activated_at_ms AS accepted_at_ms FROM character_guild_daily_quests "
        "WHERE character_id=%s AND definition_id=ANY(%s)) clocks GROUP BY definition_id",
        (character_id, sorted(identities)) * 3,
    ).fetchall()
    return {row["definition_id"]: row["accepted_at_ms"] for row in rows}


def reconcile(db, character_id, state, *, before=None, now_ms=None, writing=False):
    """Enrich canonical state inside its existing owner-locked transaction."""
    validate(state)
    prior = state if before is None else before
    unknown = set(state.get("active_unknown", prior.get("active_unknown", ())))
    active = set(state.get("active", prior.get("active", ())))
    if "active" not in state:
        active.update(state["running"])
    elif writing and before is None:
        active.update(state["running"])
    elif before is not None:
        active.update(set(state["running"]) - set(prior["running"]))
    completed = set(state["completed"])
    # Completion is separate. Removal without completion is an explicit reset,
    # cancellation or provider expiry and must deactivate the independent bit.
    removed = set(prior["running"]) - set(state["running"]) - completed
    removed |= set(prior["completed"]) - completed - set(state["running"])
    active.difference_update(removed)
    recoverable = {
        identity
        for identity in completed
        if str(identity) in state["completion_dates"]
        and (
            "active" not in state
            or before is not None
            and identity not in prior["completed"]
        )
    }
    native = _native(db, active | recoverable)
    for identity in recoverable:
        definition = native.get(identity, {})
        if (
            definition.get("native_class") == "aJM"
            and definition.get("cjT") == 0
            and definition.get("cjU") == 0
        ):
            # A native nonperiodic record with an owned completion receipt was
            # previously activated by this engine; no date is reused as a clock.
            active.add(identity)
    if "active" not in state:
        unknown.update(completed - active)
    unknown.intersection_update(completed - active)
    periods = {}
    anchored = {
        identity
        for identity in active
        if type(native.get(identity, {}).get("cjT")) is int
        and native[identity]["cjT"] > 0
    }
    clocks = _acceptance_clocks(db, character_id, anchored)
    for identity in anchored:
        definition = native[identity]
        period = definition.get("cjU")
        if type(period) is not int or period <= 0:
            raise ValueError("Invalid native achievement reset period")
        previous = state.get("active_periods", {}).get(str(identity), {})
        periods[str(identity)] = dict(
            anchor_ms=definition["cjT"],
            period_seconds=period,
            accepted_at_ms=clocks.get(identity, previous.get("accepted_at_ms")),
        )
    state["active"], state["active_periods"] = sorted(active), periods
    state["active_unknown"] = sorted(unknown)
    state["running"] = [value for value in state["running"] if value in active]
    if now_ms is None:
        now_ms = time.time_ns() // 1000000
    expired = {
        identity
        for identity in anchored
        if periods[str(identity)]["accepted_at_ms"] is not None
        and not active_status(state, identity, now_ms=now_ms)
    }
    if expired:
        state["active"] = sorted(active - expired)
        state["running"] = [value for value in state["running"] if value not in expired]
        for identity in expired:
            state["active_periods"].pop(str(identity))
    return state
