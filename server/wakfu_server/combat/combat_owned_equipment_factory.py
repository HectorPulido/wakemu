"""Preview-aware composition for every owned, NPC and expiration factory call."""
from copy import copy
from functools import lru_cache
import json

from .combat_owned_equipment import compiled_with_sources
from .combat_owned_equipment_pin import pinned_sources, _plain
from .combat_static_catalogs import ImmutableCatalog


@lru_cache(maxsize=32)
def _compiled_sources(compiled, encoded_effects):
    # The bounded cache owns only static metadata: no fight, actor, adapter,
    # transaction RNG, database authority or callback enters this key/value.
    definitions = ImmutableCatalog({"effects": json.loads(encoded_effects)})["effects"]
    return compiled_with_sources(compiled, ({"effects": definitions},))


class OwnedEquipmentRuntimeFactory:
    """Delegate unchanged when unpinned; bind definitions to the actual preview.

    In particular expiration providers do not need to capture a fight from an
    earlier readiness stage. Only factory(preview, plan) knows the committed
    candidate being processed. Application is still explicit in the owned
    initializer; this wrapper never activates a source or changes statistics.
    """

    __slots__ = ("_factory", "_compiled")

    def __init__(self, factory, compiled):
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_compiled", compiled)

    def __getattr__(self, name):
        return getattr(self._factory, name)

    def __copy__(self):
        # Existing copied-equipment constructors clone a factory, then bind
        # their own effects/state_catalog. Setters must affect that clone only.
        return type(self)(copy(self._factory), self._compiled)

    def __setattr__(self, name, value):
        if name in self.__slots__:
            object.__setattr__(self, name, value)
        else:
            setattr(self._factory, name, value)

    def __call__(self, preview, plan):
        sources = pinned_sources(
            preview, self._compiled, self._factory.characteristic_registry
        )
        if not sources:
            return self._factory(preview, plan)
        from .combat_effect_runtime import _merge_effects

        definitions = {}
        for source in sources:
            definitions = _merge_effects(definitions, {"effects": source["effects"]})
        # Equipment UIDs and actor ownership remain in the fight pin, not in
        # a process cache. Identical definitions can serve different owners.
        encoded = json.dumps(
            _plain(definitions), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        if self._factory.effects is self._compiled.effects:
            effects = _compiled_sources(self._compiled, encoded).effects
        else:
            # Preserve private copied-equipment definition overlays. They are
            # not a process-cache input and may belong to one constructor call.
            from .combat_native_area_metadata import merge_native_point_areas

            effects = merge_native_point_areas(
                _merge_effects(self._factory.effects, {"effects": definitions})
            )
        nested = copy(self._factory)
        nested.effects = effects
        # Preserve all providers, callbacks and transaction RNG. These two
        # authorities also own a definition view, so clone that view binding.
        for name in ("relative_group_children", "random_group_children"):
            authority = getattr(self._factory, name, None)
            if authority is not None:
                if not hasattr(authority, "effects"):
                    raise ValueError(
                        "Missing equipment-aware group definition authority"
                    )
                bound = copy(authority)
                bound.effects = effects
                setattr(nested, name, bound)
        return nested(preview, plan)
