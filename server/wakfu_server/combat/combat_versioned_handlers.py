"""Mutation-versioned handlers used only by the sealed native runtime factory."""
from collections.abc import MutableMapping


class NativeVersionedHandlers(MutableMapping):
    """Ordered mutable mapping with O(1) change observation.

    The native runtime factory creates this mapping before registering handlers;
    the dispatcher and its closures share this exact mapping. Direct/custom
    dispatchers continue using their original handler objects.
    """

    __slots__ = ("_data", "_version", "_mutation_depth")

    def __init__(self, values=()):
        object.__setattr__(self, "_data", dict(values))
        object.__setattr__(self, "_version", 0)
        object.__setattr__(self, "_mutation_depth", 0)

    def __setattr__(self, name, value):
        raise AttributeError("Native handler registry fields are private")

    def __delattr__(self, name):
        raise AttributeError("Native handler registry fields are private")

    @property
    def version(self):
        return object.__getattribute__(self, "_version")

    @property
    def mutation_in_progress(self):
        return object.__getattribute__(self, "_mutation_depth") != 0

    def _begin_mutation(self):
        object.__setattr__(self, "_mutation_depth", self._mutation_depth + 1)

    def _finish_mutation(self):
        object.__setattr__(self, "_version", self._version + 1)
        object.__setattr__(self, "_mutation_depth", self._mutation_depth - 1)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._begin_mutation()
        try:
            self._data[key] = value
        finally:
            self._finish_mutation()

    def __delitem__(self, key):
        self._begin_mutation()
        try:
            del self._data[key]
        finally:
            self._finish_mutation()

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()

    def clear(self):
        if self._data:
            self._begin_mutation()
            try:
                self._data.clear()
            finally:
                self._finish_mutation()

    def pop(self, key, *default):
        self._begin_mutation()
        try:
            return self._data.pop(key, *default)
        finally:
            self._finish_mutation()

    def popitem(self):
        self._begin_mutation()
        try:
            return self._data.popitem()
        finally:
            self._finish_mutation()

    def setdefault(self, key, default=None):
        self._begin_mutation()
        try:
            return self._data.setdefault(key, default)
        finally:
            self._finish_mutation()

    def update(self, values=(), /, **kwargs):
        self._begin_mutation()
        try:
            self._data.update(values, **kwargs)
        finally:
            self._finish_mutation()

    def __ior__(self, values):
        self.update(values)
        return self

    def copy(self):
        return dict(self._data)

    def __repr__(self):
        return repr(self._data)
