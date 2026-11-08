"""Operation-local native removal closure, validated before any mutation."""
from .combat_retained_query import IndexedRouting, prepare_routing, manager_query


class NativeRetainedRemovalView:
    """Only the transitive removal closure; not a complete fight population."""

    def __init__(self, fight, entries):
        self.fight = fight
        self.entries = tuple(entries)
        self.by_uid = {entry.uid: entry for entry in self.entries}


def removal_view(retention, selected):
    from types import MethodType
    from .combat_stat_handler import NativeStatHandler, _SOURCE_REMOVE

    handler = retention.stat_handler
    if type(handler) is not NativeStatHandler:
        return None
    remove = handler.remove
    if (
        type(remove) is not MethodType
        or remove.__self__ is not handler
        or remove.__func__ is not _SOURCE_REMOVE
    ):
        return None
    fight = retention.fight
    routing = prepare_routing(fight)
    if type(routing) is not IndexedRouting:
        return None
    owner = routing.owner
    managers = {}
    closure = {}
    active = set()

    def manager(identity):
        if identity not in managers:
            view = manager_query(fight, identity, _routing=routing)
            if view is None:
                raise _OpaqueClosure
            managers[identity] = view
        return managers[identity]

    def visit(uid):
        if uid in active:
            raise ValueError("Recursive native retained ownership")
        if uid in closure:
            return
        identity = owner.managers.get(uid)
        if type(identity) is not int:
            raise _OpaqueClosure
        entry = manager(identity).by_uid.get(uid)
        if entry is None:
            raise _OpaqueClosure
        children = owner.owned_children(uid)
        if children is None:
            raise _OpaqueClosure
        active.add(uid)
        if entry.effect_class == 802:
            from .combat_movement_link import movement_link_removal_dependencies

            row = fight.owned_stat_effects.get(uid)
            if row is None:
                raise _OpaqueClosure
            source, target = row["caster_id"], row["target_id"]
            other = target if entry.manager_id == source else source
            dependencies = movement_link_removal_dependencies(
                fight, entry, manager(other).entries
            )
            for dependent in dependencies:
                if dependent not in active:
                    visit(dependent)
        for child in children:
            visit(child)
        active.remove(uid)
        closure[uid] = entry

    try:
        for entry in selected:
            visit(entry.uid)
    except _OpaqueClosure:
        return None
    finally:
        # Recursive local functions otherwise retain the Fight through their
        # own closure cell after this synchronous query returns or raises.
        visit = None
    # Native removal reuses its existing depth-first dependency planner. Its
    # children and counter-manager candidates must retain global Qf order.
    entries = sorted(closure.values(), key=lambda entry: owner.ordinals[entry.uid])
    return NativeRetainedRemovalView(fight, entries)


class _OpaqueClosure(Exception):
    pass
