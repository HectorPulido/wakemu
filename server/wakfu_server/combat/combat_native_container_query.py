"""Current UID-local state/container reads through native mutation indexes."""
from .combat_state_ledger import RunningState, StateLedger
from .combat_state_managers import state_manager, state_managers
from .combat_source_parent_index import SourceParentIndex, SOURCE_MAPS

_SOURCE_MANAGER = state_manager
_SOURCE_MANAGERS = state_managers
_SOURCE_PARENTS = SourceParentIndex.parents


def _owner(fight, uid):
    from . import combat_native_container as source
    from . import combat_state_managers as managers
    from .combat_retained_registration_scope import native_membership_owner

    if (
        type(uid) is not int
        or source.state_manager is not _SOURCE_MANAGER
        or source.state_managers is not _SOURCE_MANAGERS
        or managers.state_manager is not _SOURCE_MANAGER
        or managers.state_managers is not _SOURCE_MANAGERS
        or RunningState.__getattribute__ is not object.__getattribute__
        or "__getattr__" in RunningState.__dict__
        or "uid" in RunningState.__dict__
    ):
        return None
    return native_membership_owner(fight)


def live_state_container(fight, uid):
    """Return (admitted, current state or None), never an archived state entry."""
    from .combat_state_membership import membership_bindings
    from .combat_area_membership import OwnedAreaRow

    owner = _owner(fight, uid)
    if owner is None:
        return False, None
    bindings = membership_bindings(owner, uid)
    # Multiple managers may have different validation failures. Preserve legacy
    # traversal/error ordering for this malformed population.
    if bindings is None or len(bindings) > 1:
        return False, None
    if not bindings:
        return True, None
    key = bindings[0]
    if type(key) is int:
        actor = owner.actors.get(key)
    elif key[0] == "detached":
        actor = owner.detached_actors.get(key[1])
    else:
        _, role, identity = key
        row = owner.area_sources[role].get(identity)
        if type(row) is not OwnedAreaRow or type(row).get is not dict.get:
            return False, None
        if (
            identity in owner.area_sources["native_effect_areas"]
            and identity in owner.area_sources["native_retired_area_managers"]
        ):
            return False, None
        actor = _SOURCE_MANAGER(fight, identity)
    if actor is None or type(actor.state_ledger) is not StateLedger:
        return False, None
    entries = actor.state_ledger.entries
    if type(entries) is not tuple:
        return False, None
    selected = None
    for entry in entries:
        if type(entry) is not RunningState or type(entry.uid) is not int:
            return False, None
        if entry.uid == uid:
            if selected is not None:
                raise ValueError("Missing unique native state effect container")
            selected = entry
    # A matching locator must still point to the actual current ledger entry.
    if selected is None:
        return False, None
    return True, selected


def has_owned_container_users(fight, uid):
    """Answer membership without constructing the ordered global child list."""
    owner = _owner(fight, uid)
    if owner is not None:
        index = owner.source_parents
        if (
            type(index) is SourceParentIndex
            and SourceParentIndex.parents is _SOURCE_PARENTS
            and "parents" not in vars(index)
        ):
            users = index.parents({name: owner.sources[name] for name in SOURCE_MAPS})
            if users is not None:
                return uid in users
    from .combat_native_container import owned_container_users

    return bool(owned_container_users(fight, uid))
