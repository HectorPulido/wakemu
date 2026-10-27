"""Original eWO PC2/3/4 constructor and applied event sets.

ffw.fZs/fZu are native max/current loss identifiers. eWO.bbx adds the
maximum identifier; fNL adds current loss only after a real current change,
and removes the maximum identifier when its applied amount is zero.
These identifiers never authorize a payment, world harvest or quest event.
"""

# eVi56/57/192 bind ffw.AP/MP/WP respectively. ffw's static initializer and
# eWO.bbx/fNL supply these values, independently of listener/item identities.
REDUCTION_EVENT_CONTRACTS = {
    56: (2, 78, 77),
    57: (3, 80, 79),
    192: (4, 70, 68),
}


def reduction_event_ids(effect, *, applied=None, current_changed=False):
    """Return one real eWO phase's events; None denotes pre-apply/muted PA."""
    family = effect.get("effect_class")
    masks = effect.get("target_masks")
    if (
        type(family) is not int
        or family not in REDUCTION_EVENT_CONTRACTS
        or not isinstance(masks, (list, tuple))
        or len(masks) < 7
        or type(current_changed) is not bool
        or (applied is not None and type(applied) is not int)
    ):
        raise ValueError("Missing original eWO resource event authority")
    extras = masks[6] or ()
    if not isinstance(extras, (list, tuple)) or any(
        type(event) is not int or event < 0 for event in extras
    ):
        raise ValueError("Invalid native eWO output event identifiers")
    _, maximum_loss, current_loss = REDUCTION_EVENT_CONTRACTS[family]
    events = {0, *extras}
    if applied is None or applied != 0:
        events.add(maximum_loss)
    # Native oy removes the declared bit even if PK extras also contained it.
    if applied == 0:
        events.discard(maximum_loss)
    if current_changed:
        events.add(current_loss)
    return tuple(sorted(events))


def available_reduction_events(factory, routes, *, phase):
    """Admit only eWO routes installed in the same ordinary native factory."""
    from .combat_equipment_operation_capability import FactoryOperationRoutes
    from .combat_equipment_retained_lifecycle import _native_factory
    from .combat_maximum_resource import (
        NativeMaximumReductionHandler,
        REDUCTION_FAMILIES,
    )
    from .combat_trigger_value_modifier import _OWNERS

    if type(phase) is not int or phase not in (1, 2, 3, 4):
        return frozenset()
    if type(routes) is not FactoryOperationRoutes:
        return frozenset()
    runtime = _native_factory(factory)
    if runtime is None or routes.factory is not runtime:
        return frozenset()
    adapter = getattr(runtime.contexts.healing_events, "__self__", None)
    if not callable(runtime.contexts.stat) or runtime.contexts.stat is not getattr(
        getattr(adapter, "cast", None), "stat", None
    ):
        return frozenset()
    selected = set()
    for family, (stat, maximum_loss, current_loss) in REDUCTION_EVENT_CONTRACTS.items():
        route = routes.routes.get(family)
        binding = _OWNERS.get(str(family))
        if (
            route is not None
            and route.factory is runtime
            and route.handler_type is NativeMaximumReductionHandler
            and isinstance(binding, dict)
            and binding.get("owner") == "eWO"
            and REDUCTION_FAMILIES.get(family) == stat
        ):
            selected.update((0, maximum_loss))
            if phase in (3, 4):
                selected.add(current_loss)
    return frozenset(selected)
