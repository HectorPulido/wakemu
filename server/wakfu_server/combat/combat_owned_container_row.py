"""Fresh captured PL descriptor; root-field aliases notify their actual map."""
from copy import deepcopy

_ROOT_FIELDS = ("uid", "caster_id", "target_id")


class OwnedContainerRow(dict):
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        if type(name) is str and name == "get" and "_root_maps" in vars(self):
            OwnedContainerRow._notify(self)

    def __delattr__(self, name):
        object.__delattr__(self, name)
        if type(name) is str and name == "get" and "_root_maps" in vars(self):
            OwnedContainerRow._notify(self)

    def __init__(self, *args, **kwargs):
        try:
            dict.__init__(self, *args, **kwargs)
        finally:
            vars(self).setdefault("_root_maps", [])
            self._notify()

    def _notify(self):
        from .combat_owned_container_facts import OwnedContainerFacts

        alive = []
        for map_ref, uid in self._root_maps:
            current = map_ref()
            if type(current) is OwnedContainerFacts and dict.get(current, uid) is self:
                current._roots_dirty.add(uid)
                alive.append((map_ref, uid))
        self._root_maps = alive

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        if type(key) is not str or key in _ROOT_FIELDS:
            self._notify()

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        if type(key) is not str or key in _ROOT_FIELDS:
            self._notify()

    def pop(self, key, *default):
        value = dict.pop(self, key, *default)
        if type(key) is not str or key in _ROOT_FIELDS:
            self._notify()
        return value

    def popitem(self):
        key, value = dict.popitem(self)
        if type(key) is not str or key in _ROOT_FIELDS:
            self._notify()
        return key, value

    def clear(self):
        dict.clear(self)
        self._notify()

    def update(self, *args, **kwargs):
        try:
            dict.update(self, *args, **kwargs)
        finally:
            self._notify()

    def setdefault(self, key, value=None):
        result = dict.setdefault(self, key, value)
        if type(key) is not str or key in _ROOT_FIELDS:
            self._notify()
        return result

    def __ior__(self, value):
        self.update(value)
        return self

    def __copy__(self):
        return type(self)(self)

    def __deepcopy__(self, memo):
        result = type(self)()
        memo[id(self)] = result
        dict.update(result, deepcopy(dict(self), memo))
        return result
