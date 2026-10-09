"""Execution-local Qe owner objects shared by native authority providers.

Native Qe.bfq keeps the actual PL/fyW object. A sibling can replace the live
state while that object remains the current iterator's owner. Nothing here is
kept as a mutable context after scope exit. An actual retained child separately
keeps an immutable, checkpointable snapshot of its original PL object.
"""
from .combat_state_managers import state_manager, state_managers
from contextlib import contextmanager
from contextvars import ContextVar

_scopes = ContextVar("native_state_container_scopes", default=())


@contextmanager
def state_container_scope(fight, entries):
    payloads = getattr(fight, "state_wire_payloads", None)
    wire = {
        uid: payloads.get(uid) if isinstance(payloads, dict) else None
        for uid in entries
    }
    token = _scopes.set(_scopes.get() + ((fight, dict(entries), wire),))
    try:
        yield
    finally:
        _scopes.reset(token)


def resolve_state_container(fight, uid):
    entries = [
        entry
        for actor in state_managers(fight)
        for entry in actor.state_ledger.entries
        if entry.uid == uid
    ]
    if len(entries) > 1:
        raise ValueError("Missing unique native state effect container")
    if entries:
        return entries[0]
    for owner, scope, wire in reversed(_scopes.get()):
        if owner is fight and uid in scope:
            return scope[uid]
    return owned_state_container(fight, uid)


def resolve_state_wire_payload(fight, uid):
    """A running iterator keeps its actual carrier rHA after Qf removal."""
    payloads = getattr(fight, "state_wire_payloads", None)
    payload = payloads.get(uid) if isinstance(payloads, dict) else None
    if payload is not None:
        return payload
    for owner, entries, wire in reversed(_scopes.get()):
        if owner is fight and uid in entries:
            return wire.get(uid)
    return None


def owned_container_users(fight, uid):
    """Live child Qe objects keep their actual PL even without a Qf carrier."""
    return tuple(
        child_uid
        for collection in (
            fight.owned_stat_effects,
            fight.native_owned_group_effects,
            getattr(fight, "native_owned_area_effects", {}),
        )
        for child_uid, row in collection.items()
        if row.get("state_uid") == uid
    )


def capture_owned_state_container(fight, uid):
    from dataclasses import asdict
    from .combat_state_ledger import RunningState

    state = resolve_state_container(fight, uid)
    if (
        not isinstance(state, RunningState)
        or state.uid != uid
        or not owned_container_users(fight, uid)
    ):
        raise ValueError("Missing actual retained child state container")
    facts = getattr(fight, "native_owned_state_containers", None)
    if not isinstance(facts, dict):
        raise ValueError("Missing own state container registry")
    row = asdict(state)
    if uid in facts and any(
        facts[uid].get(key) != row[key]
        for key in ("uid", "reference", "caster_id", "target_id")
    ):
        raise ValueError("Native state container UID was rebound")
    facts[uid] = row


def owned_state_container(fight, uid):
    """Attest a PL snapshot only while an actual owned child keeps it alive."""
    from .combat_state_ledger import RunningState
    from .combat_state_timing import StateTimer

    facts = getattr(fight, "native_owned_state_containers", None)
    if (
        not isinstance(facts, dict)
        or uid not in facts
        or not owned_container_users(fight, uid)
    ):
        raise ValueError("Missing unique native state effect container")
    row = dict(facts[uid])
    if (
        type(row.get("uid")) is not int
        or row["uid"] != uid
        or type(row.get("reference")) is not int
        or row["reference"] <= 0
        or type(row.get("level")) is not int
        or not 0 <= row["level"] <= 32767
        or row.get("caster_id") not in fight.actors
        or state_manager(fight, row.get("target_id")) is None
    ):
        raise ValueError("Invalid owned native state container identity")
    row["effect_ids"] = tuple(row["effect_ids"])
    if row["timer"] is not None:
        row["timer"] = StateTimer(**row["timer"])
    return RunningState(**row)
