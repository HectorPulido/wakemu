"""Query-local NPC source ancestry over current native owned UID locators."""
from types import SimpleNamespace
from .combat_source_provenance_entries import SourceProvenanceEntries


class _Decline(Exception):
    pass


def _primitive_record(row):
    return (
        type(row) is dict
        and all(type(key) is str for key in row)
        and all(
            any(type(value) is kind for kind in (int, str, bool, type(None)))
            for value in row.values()
        )
    )


class _Areas:
    """Read the same active-over-retired precedence without copying history."""

    def __init__(self, owner):
        self.owner = owner

    def get(self, identity):
        if identity is None:
            return None
        if type(identity) is not int:
            raise _Decline()
        from .combat_area_membership import OwnedAreaRow

        row = self.owner.area_sources["native_effect_areas"].get(identity)
        if row is None:
            row = self.owner.area_sources["native_retired_area_managers"].get(identity)
        if row is not None and (
            type(row) is not OwnedAreaRow
            or type(row.get("uid")) is not int
            or row["uid"] != identity
            or (
                type(row.get("effect_uid")) is not int
                and row.get("effect_uid") is not None
            )
        ):
            raise _Decline()
        return row


def selected_source_query(fight, identity):
    """Return selected entries plus exact ancestors, or decline to legacy.

    No eligibility result survives the query. The native owner supplies UID
    routing only; every relevant carrier, wire, PL and source row is rechecked.
    """
    try:
        return _selected_source_query(fight, identity)
    except _Decline:
        return None


def _selected_source_query(fight, identity):
    from .combat_retained_collections import bound_collections, bound_area_collections
    from .combat_retained_query import manager_query, prepare_routing, IndexedRouting
    from .combat_retained_source_provenance import (
        POLICY,
        _validate_record,
        _verify_wire_payload,
    )
    from .combat_state_parameters import pack_state_identity
    from .combat_state_managers import state_manager
    from .combat_state_ledger import RunningState

    owner = bound_collections(vars(fight))
    if (
        owner is None
        or not owner.valid
        or not bound_area_collections(vars(fight), owner)
    ):
        raise _Decline()
    ledger = getattr(fight, "native_state_source_provenance", None)
    if ledger is None:
        stored = None
    elif (
        type(ledger) is not dict
        or any(type(key) is not str for key in ledger)
        or set(ledger) != {"policy", "entries"}
        or type(ledger["policy"]) is not str
        or ledger["policy"] != POLICY
        or type(ledger["entries"]) is not SourceProvenanceEntries
        or SourceProvenanceEntries.__getattribute__ is not dict.__getattribute__
    ):
        raise _Decline()
    else:
        stored = ledger["entries"]
        attributes = vars(stored)
        if (
            any(type(key) is not str for key in attributes)
            or set(attributes) != {"_native_keys", "_native_key_serial"}
            or attributes["_native_keys"] is not True
            or type(attributes["_native_key_serial"]) is not int
        ):
            raise _Decline()
    routing = prepare_routing(fight)
    if type(routing) is not IndexedRouting:
        raise _Decline()
    selected = manager_query(fight, identity, _routing=routing)
    if selected is None:
        raise _Decline()
    selected_uids = frozenset(entry.uid for entry in selected.entries)
    managers = {identity: {entry.uid: entry for entry in selected.entries}}
    entries, provenance, carriers = {}, {}, {}
    areas = _Areas(owner)
    pending = list(selected_uids)
    seen = set()

    def area_parent(record):
        if (
            record.get("container_kind") != "effect_area"
            and record.get("container_type") != 3
        ):
            return None
        area = areas.get(record.get("container_id"))
        return None if area is None else area.get("effect_uid")

    while pending:
        uid = pending.pop()
        if uid in seen:
            continue
        seen.add(uid)
        record = owner.records.get(uid)
        if record is not None:
            manager_id = record.get("manager_id")
            if type(manager_id) is not int:
                raise _Decline()
            if manager_id not in managers:
                query = manager_query(fight, manager_id, _routing=routing)
                if query is None:
                    raise _Decline()
                managers[manager_id] = {entry.uid: entry for entry in query.entries}
            entry = managers[manager_id].get(uid)
            if entry is None:
                raise ValueError(
                    "Source dependency missing from actual retained manager"
                )
            entries[uid] = entry
            pending.extend(
                parent
                for parent in (entry.owner_uid, area_parent(vars(entry)))
                if parent is not None
            )
            if entry.effect_class == 310:
                manager = state_manager(fight, manager_id)
                if manager is None:
                    raise ValueError("Missing selected source carrier manager")
                states = tuple(
                    state for state in manager.state_ledger.entries if state.uid == uid
                )
                if len(states) != 1 or type(states[0]) is not RunningState:
                    raise ValueError("Missing unique selected source carrier")
                carriers[uid] = states[0]
        row = None if stored is None else dict.get(stored, str(uid))
        if row is None:
            continue
        if not _primitive_record(row):
            raise _Decline()
        _validate_record(row)
        if row["uid"] != uid:
            raise ValueError("State source UID key differs from captured identity")
        wire = fight.state_wire_payloads.get(uid)
        if wire is not None:
            _verify_wire_payload(wire, row)
        provenance[uid] = dict(row)
        pending.extend(
            parent
            for parent in (row["parent_state_uid"], area_parent(row))
            if parent is not None
        )
    # Reproduce the actual parent/PL and cycle authority on this dependency
    # closure, including archived ancestors without a current retained entry.
    for row in provenance.values():
        parent_uid = row["parent_state_uid"]
        if parent_uid is None:
            continue
        parent = provenance.get(parent_uid)
        if parent is None:
            raise ValueError("Unknown state source parent UID")
        if (
            not row["container_known"]
            or row["container_present"] is not True
            or row["container_type"] != 1
            or row["container_id"]
            != pack_state_identity(parent["state_reference"], parent["state_level"])
        ):
            raise ValueError("State source parent UID contradicts its actual native PL")
    complete = set()
    for uid in provenance:
        visiting, current = set(), uid
        while current not in complete:
            if current not in provenance:
                raise ValueError("Unknown state source parent UID")
            if current in visiting:
                raise ValueError("Cyclic state source UID ancestry")
            visiting.add(current)
            parent = provenance[current]["parent_state_uid"]
            if parent is None:
                break
            current = parent
        complete.update(visiting)
    return SimpleNamespace(
        entries=tuple(
            entries[uid] for uid in sorted(entries, key=owner.ordinals.__getitem__)
        ),
        provenance=provenance,
        carriers=carriers,
        selected_uids=selected_uids,
        areas=areas,
    )
