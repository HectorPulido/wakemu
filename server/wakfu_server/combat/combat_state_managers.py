"""Actual eHg/Qf state managers: fighters and registered faV areas.

An area is not a fighter and never receives invented HP, resources or turns.
The view is execution-local; only its owned StateLedger is checkpointed in Qq.
"""
from types import SimpleNamespace
from functools import lru_cache
from importlib import import_module
from .combat_state_ledger import StateLedger
from .combat_area_contracts import AREA_CONTRACTS, SUPPORTED_AREA_CONTRACTS


from contextlib import contextmanager
from contextvars import ContextVar

_area_pv_scopes = ContextVar("native_area_pv_scopes", default=())


@lru_cache(maxsize=16)
def _dependency_module(name):
    """Bind modules lazily for import cycles; never retain PVs or guard results."""
    return import_module("." + name, __package__)


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


@contextmanager
def selected_area_pv_scope(fight, identities):
    """Hold actual selected PV pointers across ordered sibling unregistration."""
    from .combat_native_actor_lookup import native_actor

    rows = []
    for identity in dict.fromkeys(identities):
        if identity is None or native_actor(fight, identity) is not None:
            continue
        row = retained_area_pv_row(fight, identity)
        if row is None:
            raise ValueError("Unknown selected native area PV")
        if row.get("uid") != identity:
            raise ValueError("Selected native area PV identity mismatch")
        # Validate the original native prototype and manager before retaining.
        registered_area_pv(fight, identity)
        rows.append((fight, row))
    token = _area_pv_scopes.set(_area_pv_scopes.get() + tuple(rows))
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
    definition = (
        _dependency_module("combat_effect_area")
        .native_effect_areas()
        .get(str(row.get("reference")))
    )
    if not isinstance(definition, dict):
        raise ValueError("Missing registered area native prototype")
    _dependency_module("combat_effect_area_geometry").refresh_area_geometry(fight, row)
    properties = _dependency_module("combat_area_property").area_properties(
        row, definition
    )
    entry_masks = definition.get("entry_masks")
    cell = row.get("cell")
    faw = None
    wall = None
    simple = None
    if definition.get("type") == "SIMPLE":
        simple = _dependency_module("combat_simple_area").verified_simple_area(
            row, definition
        )
    if definition.get("type") == "FAKE_FIGHTER":
        faw = _dependency_module("combat_fake_fighter").verified_fake_fighter(
            row, definition
        )
    if definition.get("type") == "ENUTROF_DEPOSIT":
        _dependency_module("combat_area_contracts").verified_deposit_grade(
            row, definition
        )
    if definition.get("type") == "WALL":
        wall = _dependency_module("combat_wall_area").verified_wall_constructor(
            row, definition, fight=fight
        )
    trap_stats = None
    if definition.get("type") == "TRAP":
        trap_stats = _dependency_module(
            "combat_trap_area"
        ).verified_trap_characteristics(row, definition)
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
        # Verified faV.rzt contains fbo objects (namespace4). Native eMo
        # queries ffe objects (namespace1), never the same numeric fbo IDs.
        # area_properties and the actual constructor were validated above.
        native_fight_properties=frozenset(),
        native_fight_affiliation=row.get("native_fight_affiliation"),
        native_running_effect_manager=row["native_running_effect_manager"],
        native_los_height=(
            faw["height"]
            if faw is not None
            else wall["bcK_value"]
            if wall is not None
            else simple["bcK_value"]
            if simple is not None
            else 0
        ),
        native_entry_masks=frozenset(entry_masks),
        state_ledger=ledger,
        native_characteristics=trap_stats,
    )


def selected_native_area_entity(fight, identity):
    """Validated Qq/eHg geometry, without fighter or invented Qf authority."""
    selected = registered_area_pv(fight, identity)
    if selected is None:
        return None
    row = retained_area_pv_row(fight, identity)
    # Qq.bcL is zero. eII.aT follows Qp.bch to its actual owner PV.
    return SimpleNamespace(
        id=identity,
        position=selected.position,
        physical_radius=0,
        owner_id=row.get("owner_id"),
        native_fight_affiliation=selected.native_fight_affiliation,
    )


def verified_native_owner_root(fight, identity, actor_authority):
    """eII.aT: verified eGj.dpu or recursive Qp.bch, never UID inference."""
    from .combat_native_actor_lookup import native_actor

    visited = set()
    while identity is not None:
        if type(identity) is not int or identity in visited or len(visited) >= 128:
            raise ValueError("Invalid or recursive native owner chain")
        visited.add(identity)
        actor = native_actor(fight, identity)
        if actor is not None:
            controller = actor_authority(actor).native_controller_id
            if type(controller) is not int:
                raise ValueError("Missing verified native owner controller")
            if controller == identity:
                return identity
            identity = controller
        else:
            if registered_area_pv(fight, identity) is None:
                raise ValueError("Unknown native owner PV")
            identity = retained_area_pv_row(fight, identity).get("owner_id")
    return None


def registered_source_pv(fight, identity):
    """Resolve the actual source PV without requiring a target-side Qf.

    A neutral faY is a valid Qe caster even though PV.bax() returns null.
    Retired areas remain usable only through their real retained checkpoint;
    this lookup neither restores Qs membership nor manufactures a ledger.
    """
    if (
        type(identity) is not int
        or identity == 0
        or not -(1 << 63) <= identity < 1 << 63
    ):
        return None
    from .combat_native_actor_lookup import native_actor

    actor = native_actor(fight, identity)
    return actor if actor is not None else registered_area_pv(fight, identity)


def state_manager(fight, identity):
    actor = fight.actors.get(identity)
    if actor is not None:
        return actor
    actor = _dependency_module("combat_summon_initialization").detached_actor(
        fight, identity
    )
    if actor is not None:
        return actor
    row = getattr(fight, "native_effect_areas", {}).get(identity)
    if row is None:
        row = getattr(fight, "native_retired_area_managers", {}).get(identity)
    if row is None:
        return None
    if row.get("native_area_contract") in ("faW", "faU", "fbd", "fbc", "fbb"):
        registered_area_pv(fight, identity)
    _dependency_module("combat_effect_area_geometry").refresh_area_geometry(fight, row)
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


def _retained_manager_users(records):
    """Index plain native references for this one callback-free prune pass.

    Custom mappings and unusual identity values retain the equality-based
    per-manager scan. This index never certifies ownership or survives a call.
    """
    if type(records) is not dict:
        return None
    users = set()
    for record in records.values():
        if type(record) is not dict:
            return None
        manager, caster = record.get("manager_id"), record.get("caster_id")
        kind = record.get("container_kind")
        if (
            manager is not None
            and type(manager) is not int
            or caster is not None
            and type(caster) is not int
            or kind is not None
            and type(kind) is not str
        ):
            return None
        users.add(manager)
        users.add(caster)
        if kind == "effect_area":
            container = record.get("container_id")
            if container is not None and type(container) is not int:
                return None
            users.add(container)
    return users


def prune_retired_state_managers(fight):
    """Release removed Qq objects only after their actual Qf/PL users vanish."""
    retired = getattr(fight, "native_retired_area_managers", {})
    if not retired:
        return
    records = getattr(fight, "native_retained_records", {})
    facts = getattr(fight, "native_owned_state_containers", {})
    from .combat_summon_initialization import detached_actors

    # Read actual ledgers, not the spatial/geometry projections of every Qq.
    # Most installed areas have null Qf and cannot hold a state carrier.
    ledgers = [
        (actor.id, getattr(actor, "state_ledger", None))
        for actor in (*fight.actors.values(), *detached_actors(fight))
    ]
    ledgers.extend(
        (identity, row.get("state_ledger"))
        for identity, row in (
            *getattr(fight, "native_effect_areas", {}).items(),
            *retired.items(),
        )
    )
    source_ids = set()
    for identity, ledger in ledgers:
        if ledger is None:
            continue
        if not isinstance(ledger, StateLedger) or ledger.actor_id != identity:
            raise ValueError("Missing actual state carrier ledger authority")
        source_ids.update(entry.caster_id for entry in ledger.entries)
    manager_users = (
        _retained_manager_users(records)
        if type(retired) is dict
        and len(retired) > 1
        and all(type(identity) is int for identity in retired)
        else None
    )
    # faV.j(PV) owns the actual source pointer, independently of Qs spatial
    # registration. A live child Qq therefore keeps its removed parent alive.
    # Start only at externally owned objects; unreachable retired cycles must
    # not keep themselves alive merely by naming each other.
    areas = getattr(fight, "native_effect_areas", {})
    pointer_roots = set(areas) | source_ids
    for record in records.values():
        for key in ("manager_id", "caster_id"):
            if type(record.get(key)) is int:
                pointer_roots.add(record[key])
        if (
            record.get("container_kind") == "effect_area"
            and type(record.get("container_id")) is int
        ):
            pointer_roots.add(record["container_id"])
    for identity, row in retired.items():
        ledger = row.get("state_ledger")
        if (
            row.get("executing")
            or row.get("removing")
            or (ledger is not None and ledger.entries)
        ):
            pointer_roots.add(identity)
    from .combat_native_container import owned_container_users

    for state in facts.values():
        if owned_container_users(fight, state.get("uid")):
            pointer_roots.update(
                value
                for value in (state.get("target_id"), state.get("caster_id"))
                if type(value) is int
            )
    pending = list(pointer_roots)
    while pending:
        identity = pending.pop()
        row = areas.get(identity, retired.get(identity))
        if row is None:
            continue
        owner = row.get("owner_id")
        if type(owner) is int and owner not in pointer_roots:
            pointer_roots.add(owner)
            pending.append(owner)
    source_ids.update(pointer_roots)
    for identity, row in tuple(retired.items()):
        if row.get("executing") or row.get("removing"):
            continue  # The actual Qq is still owned by a synchronous stack.
        ledger = row.get("state_ledger")
        if ledger is not None and ledger.entries:
            continue
        if identity in source_ids:
            continue  # A live state carrier still holds this actual source PV.
        if (
            identity in manager_users
            if manager_users is not None
            else any(
                record.get("manager_id") == identity
                or record.get("caster_id") == identity
                or (
                    record.get("container_kind") == "effect_area"
                    and record.get("container_id") == identity
                )
                for record in records.values()
            )
        ):
            continue
        from .combat_native_container import owned_container_users

        if any(
            (state.get("target_id") == identity or state.get("caster_id") == identity)
            and owned_container_users(fight, state.get("uid"))
            for state in facts.values()
        ):
            continue
        del retired[identity]
