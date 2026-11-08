"""Owner-local scalar certificates; never actor, ledger or payload authority."""
from weakref import ReferenceType, WeakKeyDictionary


class SelectedScalarProofs:
    def __init__(self):
        self.managers = {}
        self.dependents = {}
        self.event_recipes = {}

    def discard(self, manager):
        self.event_recipes.pop(manager, None)
        previous = self.managers.pop(manager, None)
        if previous is None:
            return
        for uid in previous[1]:
            bucket = self.dependents[uid]
            bucket.discard(manager)
            if not bucket:
                del self.dependents[uid]

    def invalidate(self, uid):
        if type(uid) is not int:
            self.event_recipes.clear()
            self.managers.clear()
            self.dependents.clear()
            return
        for manager in tuple(self.dependents.get(uid, ())):
            self.discard(manager)

    def install(self, manager, ids, dependencies):
        self.discard(manager)
        dependencies = frozenset(dependencies)
        self.managers[manager] = (ids, dependencies)
        for uid in dependencies:
            self.dependents.setdefault(uid, set()).add(manager)

    def matches(self, manager, ids):
        previous = self.managers.get(manager)
        return previous is not None and previous[0] == ids


def invalidate_owner(owner, uid):
    from .combat_retained_collections import RetainedCollections

    if type(owner) is RetainedCollections:
        proof = vars(owner).get("_selected_scalar_proofs")
        if type(proof) is SelectedScalarProofs:
            proof.invalidate(uid)


def invalidate_record(row):
    fields = vars(row)
    reference = fields.get("_owner_ref")
    if type(reference) is ReferenceType and type(fields.get("uid")) is int:
        invalidate_owner(reference(), fields["uid"])


def invalidate_source(row):
    from .combat_source_parent_index import SourceParentIndex
    from .combat_retained_collections import OwnedMap

    watchers = vars(row).get("_parent_watchers")
    if type(watchers) is not WeakKeyDictionary:
        return
    for index, tokens in tuple(watchers.items()):
        if type(index) is not SourceParentIndex or type(index.maps) is not dict:
            continue
        for name, uid in tokens:
            rows = index.maps.get(name)
            if type(rows) is OwnedMap and dict.get(rows, uid) is row:
                reference = vars(rows).get("_owner_ref")
                if type(reference) is ReferenceType:
                    invalidate_owner(reference(), uid)


def record_observed(owner, uid, row):
    from .combat_retained_collections import TrackedRow

    if type(row) is not TrackedRow:
        return False
    fields = vars(row)
    reference = fields.get("_owner_ref")
    return (
        type(reference) is ReferenceType
        and reference() is owner
        and type(fields.get("uid")) is int
        and fields["uid"] == uid
    )


def source_observed(owner, name, uid, row):
    from .combat_retained_collections import OwnedMap
    from .combat_source_parent_index import OwnedStateSourceRow, SourceParentIndex

    if type(row) is not OwnedStateSourceRow:
        return False
    index = owner.source_parents
    watchers = vars(row).get("_parent_watchers")
    if (
        type(index) is not SourceParentIndex
        or type(index.maps) is not dict
        or type(index.bindings) is not dict
        or type(watchers) is not WeakKeyDictionary
    ):
        return False
    rows = index.maps.get(name)
    if type(rows) is not OwnedMap or dict.get(rows, uid) is not row:
        return False
    reference = vars(rows).get("_owner_ref")
    tokens = watchers.get(index)
    return (
        type(reference) is ReferenceType
        and reference() is owner
        and type(tokens) is set
        and (name, uid) in tokens
        and index.bindings.get((name, uid)) is row
    )


def invalidate_ledger_recipes(owner, manager, uids):
    """Ledger mutations affect this manager and children witnessing its UIDs."""
    from .combat_retained_collections import RetainedCollections

    if type(owner) is not RetainedCollections:
        return
    proof = vars(owner).get("_selected_scalar_proofs")
    if type(proof) is not SelectedScalarProofs:
        return
    if type(manager) is int:
        proof.event_recipes.pop(manager, None)
    if uids is None:
        proof.event_recipes.clear()
        return
    for uid in uids:
        for dependent in proof.dependents.get(uid, ()):
            proof.event_recipes.pop(dependent, None)
