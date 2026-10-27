"""Admission evidence for installed native producers, without publishing events.

The static index reads original output masks without materializing lazy catalog
views. It retains only source identities, families and output identifiers; live
factory, roster and callback authority are checked afresh on every assessment.
"""

from collections.abc import Mapping
from threading import RLock
import weakref

_CACHE = {}
_LOCK = RLock()


def _rows(source):
    selected = {}
    for reference, row in source.items():
        if not isinstance(row, Mapping):
            continue
        family, masks = row.get("effect_class"), row.get("target_masks")
        if (
            type(family) is int
            and isinstance(masks, (tuple, list))
            and len(masks) == 7
            and isinstance(masks[6], (tuple, list))
            and masks[6]
            and all(type(event) is int and event >= 0 for event in masks[6])
        ):
            selected[reference] = (family, frozenset(masks[6]))
    return selected


def original_output_index(catalog):
    """Index only recognized immutable sources, including overriding deletions."""
    from .combat_static_catalogs import ImmutableCatalog, DefinitionOverlay
    from .combat_published_catalogs import (
        PublishedStaticMapping,
        published_original_output_index,
    )

    if type(catalog) is PublishedStaticMapping:
        return published_original_output_index(catalog)
    if type(catalog) not in (ImmutableCatalog, DefinitionOverlay):
        return {}
    identity = id(catalog)
    with _LOCK:
        existing = _CACHE.get(identity)
        if existing is not None and existing[0]() is catalog:
            return existing[1]
        if type(catalog) is ImmutableCatalog:
            result = _rows(catalog._source)
        else:
            if type(catalog._base) not in (
                ImmutableCatalog,
                DefinitionOverlay,
                PublishedStaticMapping,
            ):
                return {}
            base = original_output_index(catalog._base)
            overrides = catalog._overrides
            if type(overrides) is ImmutableCatalog:
                overrides = overrides._source
            elif type(overrides) is not dict:
                # Arbitrary mapping callbacks are not static source authority.
                return {}
            result = {key: row for key, row in base.items() if key not in overrides}
            result.update(_rows(overrides))
        from types import MappingProxyType

        result = MappingProxyType(result)

        def discard(reference, *, identity=identity):
            with _LOCK:
                entry = _CACHE.get(identity)
                if entry is not None and entry[0] is reference:
                    _CACHE.pop(identity, None)

        _CACHE[identity] = (weakref.ref(catalog, discard), result)
        return result


def available_original_events(factory, routes, *, phase, family=None):
    """Prove actual summon, displacement and original output-mask producers."""
    from .combat_equipment_operation_capability import FactoryOperationRoutes

    if type(routes) is not FactoryOperationRoutes:
        return frozenset()
    from .combat_equipment_retained_lifecycle import _native_factory
    from .combat_runtime_adapter import NativeServerRuntimeAdapter
    from .combat_summon import ordinary_roster_authority
    from .combat_stat_handler import NativeStatHandler
    from .combat_carry_handler import NativeCarryHandler
    from .combat_displacement import NativeDisplacementHandler
    from .combat_displacement_events import BASE_EVENT_IDS
    from .combat_summon_handler import NativeSummonHandler

    runtime = _native_factory(factory)
    if (
        phase not in (1, 2, 3, 4)
        or runtime is None
        or type(routes) is not FactoryOperationRoutes
        or routes.factory is not runtime
    ):
        return frozenset()
    callback = runtime.contexts.healing_events
    adapter = getattr(callback, "__self__", None)
    if (
        not isinstance(adapter, NativeServerRuntimeAdapter)
        or getattr(callback, "__func__", None)
        is not NativeServerRuntimeAdapter.healing_events
        or runtime.summon_authority is not adapter.actor_authority
        or not ordinary_roster_authority(adapter.actor_authority)
        or runtime.contexts.stat is not adapter.cast.stat
    ):
        return frozenset()

    def installed(family, handler):
        route = routes.routes.get(family)
        return (
            route is not None
            and route.factory is runtime
            and route.handler_type is handler
        )

    selected = set()
    if family in (None, 307) and installed(307, NativeSummonHandler):
        selected.add(2130)
    displacement = runtime.displacement_authority is adapter.actor_authority
    if displacement:
        for source_family, events in BASE_EVENT_IDS.items():
            if family in (None, source_family) and installed(
                source_family, NativeDisplacementHandler
            ):
                selected.update(events)
    registry = runtime.characteristic_registry.get(
        "effects", runtime.characteristic_registry
    )
    for source_family, events in original_output_index(runtime.effects).values():
        if family is not None and source_family != family:
            continue
        # eXE forwards native aZO at each actual Qe lifecycle phase. Other
        # current-stat runners have distinct current-value event constructors.
        binding = registry.get(str(source_family))
        if (
            installed(source_family, NativeStatHandler)
            and isinstance(binding, Mapping)
            and binding.get("runner") == "eXE"
        ):
            selected.update(events)
        elif (
            displacement
            and source_family in (333, 334)
            and installed(source_family, NativeCarryHandler)
        ):
            selected.update(events)
        elif (
            displacement
            and source_family in BASE_EVENT_IDS
            and installed(source_family, NativeDisplacementHandler)
        ):
            selected.update(events)
        elif source_family == 307 and installed(source_family, NativeSummonHandler):
            selected.update(events)
    return frozenset(selected)


def available_paid_breeze_events(factory, routes, retained_container, *, phase):
    """The typed ordinary lifecycle installs fad only for paid post phases."""
    from .combat_equipment_operation_capability import FactoryOperationRoutes

    if phase not in (3, 4) or type(routes) is not FactoryOperationRoutes:
        return frozenset()
    # This same check proves the exact factory's ordinary healing lifecycle;
    # its construction installs NativeBreezePaymentEvents.from_healing.
    from .combat_equipment_retained_lifecycle import preflight

    if not preflight(factory, retained_container):
        return frozenset()
    from .combat_equipment_operation_capability import FactoryOperationRoutes
    from .combat_equipment_retained_lifecycle import _native_factory

    runtime = _native_factory(factory)
    if type(routes) is not FactoryOperationRoutes or routes.factory is not runtime:
        return frozenset()
    return frozenset((2246,))
