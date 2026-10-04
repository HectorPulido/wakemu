"""Read-only static definition views; never share transaction context or RNG."""
from collections.abc import Mapping
from functools import lru_cache
import json
from .paths import DATA_ROOT


class ImmutableCatalog(dict):
    """Asset-backed read-only JSON view, freezing nested values on first read.

    Assets are process-lifetime immutable sources. Keeping unused level export
    arrays lazy avoids copying the entire state catalogue during startup.
    """
    def __init__(self, source):
        dict.__init__(self, source)
        self._source = source
        self._views = {}

    def __getitem__(self, key):
        value = self._source[key]
        if isinstance(value, (dict, list)):
            if key not in self._views:
                self._views[key] = _freeze(value)
            return self._views[key]
        return value

    def __iter__(self):
        return iter(self._source)

    def __len__(self):
        return len(self._source)

    def get(self, key, default=None):
        return self[key] if key in self else default

    def items(self):
        return ((key, self[key]) for key in self)

    def values(self):
        return (self[key] for key in self)

    def _readonly(self, *args, **kwargs):
        raise TypeError("Native static catalog is read-only")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _readonly

    def __deepcopy__(self, memo):
        return self


def _freeze(value):
    if isinstance(value, dict):
        return ImmutableCatalog(value)
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@lru_cache(maxsize=1)
def characteristic_registry():
    return ImmutableCatalog(json.loads(
        (DATA_ROOT / 'effect-characteristic-registry.json').read_text()))


class CompiledEffects:
    def __init__(self, effects, state_catalog):
        from .combat_effect_runtime import _merge_effects
        from .combat_native_area_metadata import merge_native_point_areas
        self.source_effects = effects
        self.source_states = state_catalog
        self.effects = ImmutableCatalog(merge_native_point_areas(
            _merge_effects(effects, state_catalog)))
