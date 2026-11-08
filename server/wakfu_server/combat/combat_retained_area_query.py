"""Fresh authority for one indexed native area, without historical traversal."""
from .combat_state_ledger import StateLedger, RunningState
from .combat_area_membership import OwnedAreaRow
from .combat_retained_collections import bound_collections, bound_area_collections


def _plain_area_value(value, seen):
    kind = type(value)
    if kind in (int, bool, float, str, bytes, type(None)):
        return True
    if kind is StateLedger:
        return (
            type(value.actor_id) is int
            and type(value.entries) is tuple
            and all(
                type(state) is RunningState and type(state.uid) is int
                for state in value.entries
            )
        )
    if id(value) in seen:
        return False
    seen.add(id(value))
    try:
        if kind is dict or kind is OwnedAreaRow:
            return all(
                type(key) in (int, str) and _plain_area_value(item, seen)
                for key, item in value.items()
            )
        if kind in (list, tuple, set, frozenset):
            return all(_plain_area_value(item, seen) for item in value)
        return False
    finally:
        seen.remove(id(value))


def selected_area_row(fight, identity):
    """Locate a current native row; this does not certify its prototype/Qf."""
    if type(identity) is not int:
        return None
    fields = vars(fight)
    owner = bound_collections(fields)
    if owner is None or not owner.valid or not bound_area_collections(fields, owner):
        return None
    row = owner.area_sources["native_effect_areas"].get(identity)
    if row is None:
        row = owner.area_sources["native_retired_area_managers"].get(identity)
    if (
        type(row) is not OwnedAreaRow
        or type(row.get("uid")) is not int
        or row.get("uid") != identity
        or not _plain_area_value(row, set())
    ):
        return None
    return row


def selected_area_manager(fight, identity, *, managers=None):
    row = selected_area_row(fight, identity)
    if row is None or type(row.get("state_ledger")) is not StateLedger:
        return None
    from .combat_state_managers import state_manager

    # Resolve the real Qq, retaining normal prototype and ledger authority.
    manager = (
        state_manager(fight, identity)
        if managers is None
        else managers.resolve(identity)
    )
    if manager is None or manager.state_ledger is not row["state_ledger"]:
        return None
    return manager


def selected_area_target(fight, identity):
    if selected_area_row(fight, identity) is None:
        return False
    from .combat_state_managers import registered_area_pv

    return registered_area_pv(fight, identity) is not None
