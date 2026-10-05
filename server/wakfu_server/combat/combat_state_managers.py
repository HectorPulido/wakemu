"""Actual eHg/Qf state managers: fighters and registered faV areas.

An area is not a fighter and never receives invented HP, resources or turns.
The view is execution-local; only its owned StateLedger is checkpointed in Qq.
"""
from types import SimpleNamespace
from .combat_state_ledger import StateLedger


def state_manager(fight, identity):
    actor = fight.actors.get(identity)
    if actor is not None:
        return actor
    row = getattr(fight, "native_effect_areas", {}).get(identity)
    if row is None:
        row = getattr(fight, "native_retired_area_managers", {}).get(identity)
    if row is None:
        return None
    if row.get("native_running_effect_manager") is False:
        return None  # Original faV.bax falls through to PV null without fbo12.
    ledger = row.get("state_ledger")
    if (
        row.get("uid") != identity
        or row.get("native_area_contract") not in ("faZ", "faY")
        or not isinstance(ledger, StateLedger)
        or ledger.actor_id != identity
    ):
        raise ValueError("Missing actual registered area state manager")
    return SimpleNamespace(
        id=identity,
        position=tuple(row["cell"]),
        state_ledger=ledger,
        native_is_area=True,
    )


def state_managers(fight):
    yield from fight.actors.values()
    active = getattr(fight, "native_effect_areas", {})
    retired = getattr(fight, "native_retired_area_managers", {})
    if set(active) & set(retired):
        raise ValueError("Area manager is both active and retired")
    for identity, row in tuple(active.items()) + tuple(retired.items()):
        if "state_ledger" not in row:
            continue  # Legacy/null Qf snapshots have no state manager.
        if identity in fight.actors:
            raise ValueError("Native area/fighter identity collision")
        yield state_manager(fight, identity)


def prune_retired_state_managers(fight):
    """Release removed Qq objects only after their actual Qf/PL users vanish."""
    retired = getattr(fight, "native_retired_area_managers", {})
    records = getattr(fight, "native_retained_records", {})
    facts = getattr(fight, "native_owned_state_containers", {})
    for identity, row in tuple(retired.items()):
        ledger = row.get("state_ledger")
        if ledger is not None and ledger.entries:
            continue
        if any(
            record.get("manager_id") == identity
            or (
                record.get("container_kind") == "effect_area"
                and record.get("container_id") == identity
            )
            for record in records.values()
        ):
            continue
        if any(state.get("target_id") == identity for state in facts.values()):
            continue
        del retired[identity]
