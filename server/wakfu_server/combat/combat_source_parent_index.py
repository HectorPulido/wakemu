"""Prototype actual-source parent counts; no retained metadata substitution.

Native producers must construct rows with this type from the outset. Never
wrap an already published caller row: its external aliases are authoritative.
Map replacement/admission and every map mutation require owner bind gateways.
"""
from copy import deepcopy, _keep_alive
from weakref import WeakKeyDictionary, ref


SOURCE_MAPS = (
    "owned_stat_effects",
    "native_owned_group_effects",
    "native_owned_area_effects",
    "native_owned_spatial_effects",
)


_SOURCE_ATOMIC_TYPES = frozenset((type(None), bool, int, float, complex, str, bytes))
_SOURCE_MEMO_MISSING = object()


def _copy_source_payload(payload, memo):
    """Copy exact native payload dictionaries with normal deepcopy ordering.

    Inline only builtin atomic leaves. Mutable/custom values and dictionary
    subclasses retain ordinary deepcopy, including their memo and callbacks.
    """
    prior = memo.get(id(payload), _SOURCE_MEMO_MISSING)
    if prior is not _SOURCE_MEMO_MISSING:
        return prior
    copied = {}
    memo[id(payload)] = copied
    for key, value in payload.items():
        # Assignment evaluates its RHS before the subscription key. Preserve
        # that order when a custom value or key observes/changes the memo.
        value_type = type(value)
        if value_type in _SOURCE_ATOMIC_TYPES:
            cloned_value = memo.get(id(value), value)
        elif value_type is dict:
            cloned_value = _copy_source_payload(value, memo)
        else:
            cloned_value = deepcopy(value, memo)
        cloned_key = (
            memo.get(id(key), key)
            if type(key) in _SOURCE_ATOMIC_TYPES
            else deepcopy(key, memo)
        )
        copied[cloned_key] = cloned_value
    # Generic deepcopy republishes its result after callbacks, then retains
    # temporary input dictionaries so their IDs cannot be reused in this memo.
    memo[id(payload)] = copied
    _keep_alive(payload, memo)
    return copied


class OwnedStateSourceRow(dict):
    def _invalidate_scalar(self):
        object.__setattr__(self, "_scalar_eligibility", None)
        from .combat_selected_scalar_proof import invalidate_source

        invalidate_source(self)

    def __setattr__(self, name, value):
        if type(name) is str and name == "_parent_watchers":
            OwnedStateSourceRow._invalidate_scalar(self)
        object.__setattr__(self, name, value)
        if type(name) is str and name in ("get", "values", "__iter__"):
            OwnedStateSourceRow._invalidate_scalar(self)
        if type(name) is str and name == "get":
            OwnedStateSourceRow._notify(self)

    def __delattr__(self, name):
        if type(name) is str and name == "_parent_watchers":
            OwnedStateSourceRow._invalidate_scalar(self)
        object.__delattr__(self, name)
        if type(name) is str and name in ("get", "values", "__iter__"):
            OwnedStateSourceRow._invalidate_scalar(self)
        if type(name) is str and name == "get":
            OwnedStateSourceRow._notify(self)

    def __init__(self, *args, **kwargs):
        OwnedStateSourceRow._invalidate_scalar(self)
        try:
            dict.__init__(self, *args, **kwargs)
        finally:
            self._notify()

    def __copy__(self):
        return type(self)(self)

    def _notify(self):
        OwnedStateSourceRow._invalidate_scalar(self)
        watchers = vars(self).get("_parent_watchers")
        if watchers is not None:
            for index, tokens in tuple(watchers.items()):
                index.dirty.update(tokens)

    def __setitem__(self, key, value):
        OwnedStateSourceRow._invalidate_scalar(self)
        try:
            dict.__setitem__(self, key, value)
        finally:
            if type(key) is not str or key == "state_uid":
                self._notify()

    def __delitem__(self, key):
        OwnedStateSourceRow._invalidate_scalar(self)
        try:
            dict.__delitem__(self, key)
        finally:
            if type(key) is not str or key == "state_uid":
                self._notify()

    def clear(self):
        OwnedStateSourceRow._invalidate_scalar(self)
        dict.clear(self)
        self._notify()

    def pop(self, key, *default):
        OwnedStateSourceRow._invalidate_scalar(self)
        try:
            return dict.pop(self, key, *default)
        finally:
            if type(key) is not str or key == "state_uid":
                self._notify()

    def popitem(self):
        OwnedStateSourceRow._invalidate_scalar(self)
        try:
            return dict.popitem(self)
        finally:
            self._notify()

    def update(self, *args, **kwargs):
        OwnedStateSourceRow._invalidate_scalar(self)
        try:
            dict.update(self, *args, **kwargs)
        finally:
            # dict.update may partially modify a mapping before raising.
            self._notify()

    def setdefault(self, key, default=None):
        OwnedStateSourceRow._invalidate_scalar(self)
        try:
            return dict.setdefault(self, key, default)
        finally:
            if type(key) is not str or key == "state_uid":
                self._notify()

    def __ior__(self, value):
        self.update(value)
        return self

    def __deepcopy__(self, memo):
        result = type(self).__new__(type(self))
        memo[id(self)] = result
        payload = dict(self)
        copied = (
            _copy_source_payload(payload, memo)
            if type(self) is OwnedStateSourceRow
            else deepcopy(payload, memo)
        )
        dict.__init__(result, copied)
        # Parent observers are derived indexes, never copied combat authority.
        return result


class SourceParentIndex:
    """Counts owned source-row state_uid values, including unregistered rows.

    Unsupported rows abstain. Native spatial rows keep their exact native
    runner and identity validation; only parent mutation notification is shared.
    """

    def __init__(self, source_maps):
        from .combat_retained_collections import OwnedMap

        self.maps = dict(source_maps)
        self.bindings = {}
        self.parents_by_token = {}
        self.counts = {}
        self.changed_parents = set()
        self.root_changed_parents = set()
        self._facts_ref = None
        self.opaque = set()
        self.dirty = set()
        self.valid = set(self.maps) == set(SOURCE_MAPS) and all(
            type(value) is dict or type(value) is OwnedMap
            for value in self.maps.values()
        )
        if self.valid:
            for name, values in self.maps.items():
                for uid in values:
                    self.bind(name, uid)

    def bind(self, name, uid):
        """Owner calls after inserting/deleting/replacing a source map entry."""
        if not self.valid or name not in self.maps or type(uid) is not int:
            self.valid = False
            return
        token = (name, uid)
        previous = self.bindings.pop(token, None)
        if previous is not None:
            watchers = vars(previous).get("_parent_watchers")
            if watchers is not None and self in watchers:
                watchers[self].discard(token)
                if not watchers[self]:
                    del watchers[self]
        row = dict.get(self.maps[name], uid)
        if _tracked_source(row):
            watchers = vars(row).setdefault("_parent_watchers", WeakKeyDictionary())
            watchers.setdefault(self, set()).add(token)
            self.bindings[token] = row
        self.dirty.add(token)

    def parents(self, source_maps):
        """Return exact integer parent membership, or None for legacy fallback."""
        if not self.valid or any(
            source_maps.get(name) is not self.maps[name] for name in SOURCE_MAPS
        ):
            return None
        for token in tuple(self.dirty):
            had_parent = token in self.parents_by_token
            old = self.parents_by_token.pop(token, None)
            if had_parent:
                self.changed_parents.add(old)
                self.root_changed_parents.add(old)
                count = self.counts[old] - 1
                if count:
                    self.counts[old] = count
                else:
                    del self.counts[old]
            self.opaque.discard(token)
            name, uid = token
            values = self.maps[name]
            if uid not in values:
                continue
            row = dict.__getitem__(values, uid)
            if (
                not _tracked_source(row)
                or self.bindings.get(token) is not row
                or type(row).get is not dict.get
                or "get" in vars(row)
                or any(type(key) is not str for key in row)
            ):
                self.opaque.add(token)
                continue
            parent = dict.get(row, "state_uid")
            if parent is not None and type(parent) is not int:
                self.opaque.add(token)
                continue
            self.changed_parents.add(parent)
            self.root_changed_parents.add(parent)
            self.parents_by_token[token] = parent
            self.counts[parent] = self.counts.get(parent, 0) + 1
        self.dirty.clear()
        return None if self.opaque else self.counts.keys()

    def prune_facts(self, facts, source_maps):
        """Prune only changed descriptor users after the first certified boundary."""
        from .combat_owned_container_facts import OwnedContainerFacts

        if (
            type(facts) is not OwnedContainerFacts
            or facts._valid is not True
            or type(facts._dirty) is not set
            or any(type(uid) is not int for uid in facts._dirty)
        ):
            self._facts_ref = None
            self.changed_parents.clear()
            return False
        users = self.parents(source_maps)
        if users is None:
            self._facts_ref = None
            self.changed_parents.clear()
            return False
        if self._facts_ref is None or self._facts_ref() is not facts:
            candidates = tuple(facts)
        else:
            candidates = self.changed_parents | facts._dirty
        for uid in candidates:
            if uid in facts and uid not in users:
                del facts[uid]
        facts._dirty.clear()
        self.changed_parents.clear()
        self._facts_ref = ref(facts)
        return True


def _tracked_source(row):
    if type(row) is OwnedStateSourceRow:
        return True
    from .combat_pointer_qi_spatialowned import NativeSpatialRecord

    return type(row) is NativeSpatialRecord
