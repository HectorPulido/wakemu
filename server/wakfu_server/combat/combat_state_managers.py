"""Actual eHg/Qf state managers: fighters and registered faV areas.

An area is not a fighter and never receives invented HP, resources or turns.
The view is execution-local; only its owned StateLedger is checkpointed in Qq.
"""
from types import SimpleNamespace
from .combat_state_ledger import StateLedger
from .combat_area_contracts import AREA_CONTRACTS, SUPPORTED_AREA_CONTRACTS


from contextlib import contextmanager
from contextvars import ContextVar

_area_pv_scopes = ContextVar("native_area_pv_scopes", default=())


@contextmanager
def removed_area_pv_scope(fight, row):
    """Keep actual Qe.bfs after Qs unregistration, without spatial membership."""
    if row.get("uid") in getattr(fight, "native_effect_areas", {}):
        raise ValueError("Removed area scope requires actual Qs unregistration")
    token = _area_pv_scopes.set(_area_pv_scopes.get() + ((fight, row),))
    try:
        yield
    finally:
        _area_pv_scopes.reset(token)


def retained_area_pv_row(fight, identity):
    row = getattr(fight, "native_effect_areas", {}).get(identity)
    if row is None:
        row = getattr(fight, "native_retired_area_managers", {}).get(identity)
    if row is None:
        for owner, candidate in reversed(_area_pv_scopes.get()):
            if owner is fight and candidate.get("uid") == identity:
                return candidate
    return row


def registered_area_pv(fight, identity):
    """Resolve an actual faV PV, independently of whether it has a Qf."""
    if identity in fight.actors:
        raise ValueError("Native area/fighter identity collision")
    active = getattr(fight, "native_effect_areas", {})
    retired = getattr(fight, "native_retired_area_managers", {})
    if identity in active and identity in retired:
        raise ValueError("Area PV is both active and retired")
    row = retained_area_pv_row(fight, identity)
    if row is None:
        return None
    from .combat_effect_area import native_effect_areas

    definition = native_effect_areas().get(str(row.get("reference")))
    if not isinstance(definition, dict):
        raise ValueError("Missing registered area native prototype")
    from .combat_effect_area_geometry import refresh_area_geometry

    refresh_area_geometry(fight, row)
    from .combat_area_property import area_properties

    properties = area_properties(row, definition)
    entry_masks = definition.get("entry_masks")
    cell = row.get("cell")
    faw = None
    wall = None
    if definition.get("type") == "FAKE_FIGHTER":
        from .combat_fake_fighter import verified_fake_fighter

        faw = verified_fake_fighter(row, definition)
    if definition.get("type") == "ENUTROF_DEPOSIT":
        from .combat_area_contracts import verified_deposit_grade

        verified_deposit_grade(row, definition)
    if definition.get("type") == "WALL":
        from .combat_wall_area import verified_wall_constructor

        wall = verified_wall_constructor(row, definition)
    trap_stats = None
    if definition.get("type") == "TRAP":
        from .combat_trap_area import verified_trap_characteristics

        trap_stats = verified_trap_characteristics(row, definition)
    if (
        row.get("uid") != identity
        or definition.get("type") not in AREA_CONTRACTS
        or row.get("native_area_contract")
        != (AREA_CONTRACTS.get(definition.get("type")))
        or not isinstance(properties, (list, tuple, set, frozenset))
        or any(type(value) is not int for value in properties)
        or not isinstance(entry_masks, (list, tuple))
        or any(type(value) is not int for value in entry_masks)
        or not isinstance(cell, (list, tuple))
        or len(cell) != 3
        or any(type(value) is not int for value in cell)
        or type(row.get("native_running_effect_manager")) is not bool
        or row["native_running_effect_manager"]
        != (
            faw["running_effect_manager"]
            if faw is not None
            else wall["running_effect_manager"]
            if wall is not None
            else 12 in properties
        )
    ):
        raise ValueError("Incomplete registered area PV authority")
    ledger = row.get("state_ledger")
    if row["native_running_effect_manager"]:
        if not isinstance(ledger, StateLedger) or ledger.actor_id != identity:
            raise ValueError("Missing actual registered area state manager")
    elif ledger is not None:
        raise ValueError("Native null-Qf area has an invented ledger")
    return SimpleNamespace(
        id=identity,
        position=tuple(cell),
        native_is_area=True,
        native_fight_affiliation=row.get("native_fight_affiliation"),
        native_running_effect_manager=row["native_running_effect_manager"],
        native_los_height=(
            faw["height"]
            if faw is not None
            else wall["bcK_value"]
            if wall is not None
            else 0
        ),
        native_entry_masks=frozenset(entry_masks),
        state_ledger=ledger,
        native_characteristics=trap_stats,
    )


def state_manager(fight, identity):
    actor = fight.actors.get(identity)
    if actor is not None:
        return actor
    from .combat_summon_initialization import detached_actor

    actor = detached_actor(fight, identity)
    if actor is not None:
        return actor
    row = getattr(fight, "native_effect_areas", {}).get(identity)
    if row is None:
        row = getattr(fight, "native_retired_area_managers", {}).get(identity)
    if row is None:
        return None
    if row.get("native_area_contract") in ("faW", "faU", "fbd", "fbc"):
        registered_area_pv(fight, identity)
    from .combat_effect_area_geometry import refresh_area_geometry

    refresh_area_geometry(fight, row)
    if row.get("native_running_effect_manager") is False:
        return None  # Original faV.bax falls through to PV null without fbo12.
    ledger = row.get("state_ledger")
    if (
        row.get("uid") != identity
        or row.get("native_area_contract") not in SUPPORTED_AREA_CONTRACTS
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
    from .combat_summon_initialization import detached_actors

    yield from detached_actors(fight)
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
