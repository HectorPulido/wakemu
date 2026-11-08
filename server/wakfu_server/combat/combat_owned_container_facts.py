"""Native descriptor membership mutations, separate from mutable descriptor values."""
from copy import deepcopy
from weakref import ref


class OwnedContainerFacts(dict):
    def __init__(self, *args, **kwargs):
        vars(self).setdefault("_roots_dirty", set())
        vars(self).setdefault("_root_opaque", set())
        vars(self).setdefault("_root_bindings", {})
        try:
            dict.__init__(self, *args, **kwargs)
        finally:
            self._dirty = set()
            self._valid = True
            self._touch_all()

    def _touch(self, key):
        if type(key) is int:
            self._dirty.add(key)
            self._touch_root(key)
        else:
            self._valid = False

    def _touch_root(self, key):
        from .combat_owned_container_row import OwnedContainerRow

        self._roots_dirty.add(key)
        self._root_opaque.discard(key)
        previous = self._root_bindings.pop(key, None)
        if previous is not None:
            previous._root_maps = [
                (watcher, uid)
                for watcher, uid in previous._root_maps
                if watcher() is not self or uid != key
            ]
        if key not in self:
            return
        row = dict.__getitem__(self, key)
        if type(row) is not OwnedContainerRow:
            self._root_opaque.add(key)
            return
        row._root_maps.append((ref(self), key))
        self._root_bindings[key] = row

    def _touch_all(self):
        for key in dict.__iter__(self):
            self._touch(key)

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self._touch(key)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self._touch(key)

    def pop(self, key, *default):
        result = dict.pop(self, key, *default)
        self._touch(key)
        return result

    def popitem(self):
        key, value = dict.popitem(self)
        self._touch(key)
        return key, value

    def clear(self):
        keys = tuple(dict.__iter__(self))
        dict.clear(self)
        for key in keys:
            self._touch(key)

    def setdefault(self, key, default=None):
        result = dict.setdefault(self, key, default)
        self._touch(key)
        return result

    def update(self, *args, **kwargs):
        try:
            dict.update(self, *args, **kwargs)
        finally:
            self._touch_all()

    def __ior__(self, value):
        self.update(value)
        return self

    def __copy__(self):
        return type(self)(self)

    def __deepcopy__(self, memo):
        result = type(self)()
        memo[id(self)] = result
        dict.update(result, deepcopy(dict(self), memo))
        result._touch_all()
        return result
