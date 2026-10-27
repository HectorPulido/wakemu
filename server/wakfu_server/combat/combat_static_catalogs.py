"""Read-only static definition views; never share transaction context or RNG."""
from wakfu_server import native_catalog as protocol_catalog
from collections.abc import Mapping
from functools import lru_cache
import json
import threading
import weakref
from wakfu_server.paths import DATA_ROOT


# Keep cached views outside ImmutableCatalog instances. Catalogs can be reachable
# from checkpointed combat objects, so populating an instance cache would mutate
# an otherwise read-only source graph during a query. The weak owner reference
# also prevents this process cache from extending a catalog's lifetime.
_VIEW_CACHE_LOCK = threading.RLock()
_VIEW_CACHE = {}


class ImmutableCatalog(dict):
    """Asset-backed read-only JSON view, freezing nested values on first read.

    Assets are process-lifetime immutable sources. Keeping unused level export
    arrays lazy avoids copying the entire state catalogue during startup.
    ``_views`` remains an empty legacy field for serialized compatibility;
    lazy views live in a weak module cache so reads never mutate the catalog.
    """

    def __init__(self, source):
        dict.__init__(self, source)
        self._source = source
        # Reserved legacy serialized field. Do not populate it: the catalog
        # may be part of a fingerprinted combat authority graph.
        self._views = {}

    def _cached_views(self):
        identity = id(self)
        with _VIEW_CACHE_LOCK:
            entry = _VIEW_CACHE.get(identity)
            if entry is not None and entry[0]() is self:
                return entry[1]

            def discard(
                reference,
                *,
                identity=identity,
                lock=_VIEW_CACHE_LOCK,
                cache=_VIEW_CACHE,
            ):
                # Weak callbacks can outlive module globals during teardown.
                with lock:
                    current = cache.get(identity)
                    if current is not None and current[0] is reference:
                        cache.pop(identity, None)

            reference = weakref.ref(self, discard)
            views = {}
            _VIEW_CACHE[identity] = (reference, views)
            return views

    def __getitem__(self, key):
        value = self._source[key]
        if isinstance(value, (dict, list)):
            views = self._cached_views()
            with _VIEW_CACHE_LOCK:
                if key not in views:
                    views[key] = _freeze(value)
                return views[key]
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

    __setitem__ = (
        __delitem__
    ) = clear = pop = popitem = setdefault = update = __ior__ = _readonly

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self


def _freeze(value):
    if isinstance(value, dict):
        return ImmutableCatalog(value)
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@lru_cache(maxsize=1)
def characteristic_registry():
    return ImmutableCatalog(
        protocol_catalog.load(DATA_ROOT / "effect-characteristic-registry.json")
    )


class DefinitionOverlay(Mapping):
    """Read-only static delta over an already qualified definition mapping."""

    def __init__(self, base, overrides, *, iteration_source=None):
        self._base = base
        self._overrides = overrides
        self._iteration_source = iteration_source
        self._size = len(base) + sum(key not in base for key in overrides)

    def __getitem__(self, key):
        if key in self._overrides:
            return self._overrides[key]
        return self._base[key]

    def __contains__(self, key):
        return key in self._overrides or key in self._base

    def __iter__(self):
        if self._iteration_source is not None:
            # The original full merge visits spell/source definitions before
            # state-only definitions, including newly attached spell roots.
            yield from self._iteration_source
            yield from (key for key in self._base if key not in self._iteration_source)
        else:
            yield from self._base
            yield from (key for key in self._overrides if key not in self._base)

    def __len__(self):
        return self._size

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self


class CompiledEffects:
    @classmethod
    def from_published(cls, variant="player"):
        """Use exact offline compiler outputs; never rebuild them in World."""
        from wakfu_server.native_compiled_catalog import (
            resolve_publication,
            descriptor_for,
        )
        from .combat_published_catalogs import (
            resolve_static_catalog_descriptor,
            static_catalog_descriptor,
        )

        publication = resolve_publication(source_revision=protocol_catalog.release())
        manifest = publication
        if variant not in ("player", "npc_imported", "npc_baseline", "weapon"):
            raise ValueError("Unknown published native combat variant")
        if manifest.get("policy") != "wakemu.compiled-combat-catalog.v1":
            raise ValueError("Invalid published native combat compiler contract")

        def collection(name):
            if type(name) is not str:
                raise ValueError("Invalid published combat collection name")
            return resolve_static_catalog_descriptor(descriptor_for(publication, name))

        rows = manifest["variants"][variant]
        compiled = object.__new__(cls)
        compiled.source_effects = collection(rows["source_effects"])
        from wakfu_server.spell_audit import states_catalog

        # Timing/dispatch use this same cached source object. Preserve the
        # existing factory identity guard across player/NPC/weapon variants.
        compiled.source_states = states_catalog()
        for field, name in (
            ("states", manifest["states"]),
            ("effects", manifest["state_effects"]),
        ):
            if static_catalog_descriptor(
                compiled.source_states.get(field)
            ) != descriptor_for(publication, name):
                raise ValueError("Published combat state source identity mismatch")
        compiled.effects = collection(rows["effects"])
        return compiled

    def __init__(self, effects, state_catalog):
        from .combat_effect_runtime import _merge_effects
        from .combat_native_area_metadata import merge_native_point_areas

        self.source_effects = effects
        self.source_states = state_catalog
        self.effects = ImmutableCatalog(
            merge_native_point_areas(_merge_effects(effects, state_catalog))
        )

    def with_effect_sources(self, effects):
        """Validate source additions while sharing the qualified immutable base.

        Ordinary source merges preserve an existing source row when its native
        identity agrees. A new source that also exists only in the state graph
        takes precedence, after the same spell/state collision validation.
        """
        from .combat_effect_runtime import _merge_effects

        missing = object()
        delta = {}
        for reference, effect in effects.items():
            existing = self.source_effects.get(reference, missing)
            if existing is effect:
                continue
            if existing is not missing:
                _merge_effects({reference: existing}, {"effects": {reference: effect}})
            else:
                delta[reference] = effect
        state_effects = self.source_states["effects"]
        overlapping_states = {
            reference: state_effects[reference]
            for reference in delta
            if reference in state_effects
        }
        if overlapping_states:
            _merge_effects(delta, {"effects": overlapping_states})
        return self.with_effect_delta(delta)

    def with_effect_delta(self, effects):
        """Compile only additional sources; the base was qualified at construction.

        Callers must first apply the ordinary source/state collision checks.
        This stores definitions only, never source ownership or execution state.
        """
        from .combat_native_area_metadata import merge_native_point_areas

        if not effects:
            return self
        extended = object.__new__(type(self))
        extended.source_effects = DefinitionOverlay(self.source_effects, dict(effects))
        extended.source_states = self.source_states
        extended.effects = DefinitionOverlay(
            self.effects,
            ImmutableCatalog(merge_native_point_areas(effects)),
            iteration_source=extended.source_effects,
        )
        return extended
