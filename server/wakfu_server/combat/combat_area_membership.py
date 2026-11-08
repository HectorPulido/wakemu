"""Native Qq row created before publication; ledger aliases stay observable."""
from copy import deepcopy


class OwnedAreaRow(dict):
    __slots__ = ("_membership_owners", "__weakref__")

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self._membership_owners = []

    def _changed(self):
        from .combat_state_membership import attach_area

        alive = []
        for owner_ref, role, key in tuple(getattr(self, "_membership_owners", ())):
            owner = owner_ref()
            if owner is None:
                continue
            if owner.area_sources[role].get(key) is self:
                alive.append((owner_ref, role, key))
                attach_area(owner, key, self, role=role)
        self._membership_owners = alive

    def _roots_changed(self):
        for owner_ref, role, key in tuple(getattr(self, "_membership_owners", ())):
            owner = owner_ref()
            if owner is not None and owner.area_sources[role].get(key) is self:
                owner.retired_tracking.area_changed(key)

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        if type(key) is not str or key == "state_ledger":
            self._changed()
        if type(key) is not str or key in (
            "owner_id",
            "executing",
            "removing",
            "state_ledger",
        ):
            self._roots_changed()

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        if type(key) is not str or key == "state_ledger":
            self._changed()
        if type(key) is not str or key in (
            "owner_id",
            "executing",
            "removing",
            "state_ledger",
        ):
            self._roots_changed()

    def pop(self, key, *default):
        result = dict.pop(self, key, *default)
        if type(key) is not str or key == "state_ledger":
            self._changed()
        if type(key) is not str or key in (
            "owner_id",
            "executing",
            "removing",
            "state_ledger",
        ):
            self._roots_changed()
        return result

    def popitem(self):
        key, value = dict.popitem(self)
        if type(key) is not str or key == "state_ledger":
            self._changed()
        if type(key) is not str or key in (
            "owner_id",
            "executing",
            "removing",
            "state_ledger",
        ):
            self._roots_changed()
        return key, value

    def clear(self):
        dict.clear(self)
        self._changed()
        self._roots_changed()

    def update(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def setdefault(self, key, value=None):
        if key not in self:
            self[key] = value
        return self[key]

    def __ior__(self, other):
        self.update(other)
        return self

    def __deepcopy__(self, memo):
        result = type(self)()
        memo[id(self)] = result
        for key, value in self.items():
            dict.__setitem__(result, deepcopy(key, memo), deepcopy(value, memo))
        return result
