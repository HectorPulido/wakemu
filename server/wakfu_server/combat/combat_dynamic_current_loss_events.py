"""Typed Wakemu publisher for resolved dynamic Stasis/Light loss sources.

Native eWR(PC).bbx declares ffw.fZu for the real PC. The eVi40 prototype
starts without PC, and its original C does not rebuild bbx. Wakemu explicitly
reconstructs the server binding after C resolves parameter2: only the actual
generic40 source's L2/L3/L4 phases gain the PC90/109 declaration. L1, unrelated
PCs and absent PA do not gain a synthetic characteristic notification.
"""

from .combat_parameters import parameter_value


DYNAMIC_CURRENT_LOSS_EVENTS = {90: 166, 109: 168}


def resolved_current_loss_events(
    effect, binding, *, level, stat_id, target_has_characteristic
):
    """Return only the declaration of one actual resolved eWR40 source."""
    if effect.get("effect_class") != 40:
        return ()
    if (
        binding.get("runner") != "eWR"
        or binding.get("fixed_stat_id") is not None
        or type(target_has_characteristic) is not bool
        or type(stat_id) is not int
    ):
        raise ValueError("Missing typed dynamic current-loss source")
    parameters = effect.get("parameters")
    if not isinstance(parameters, (tuple, list)) or len(parameters) != 6:
        raise ValueError("Missing native dynamic current-loss PC parameter")
    resolved = parameter_value(parameters, 2, level) & 255
    if resolved != stat_id:
        raise ValueError("Dynamic current-loss PC differs from actual runner plan")
    if not target_has_characteristic or stat_id not in DYNAMIC_CURRENT_LOSS_EVENTS:
        return ()
    return (DYNAMIC_CURRENT_LOSS_EVENTS[stat_id],)


def available_dynamic_current_loss_events(factory, routes, *, phase):
    """Admit the reconstructed declaration only on its installed owned route."""
    if type(phase) is not int or phase not in (2, 3, 4):
        return frozenset()
    from .combat_equipment_operation_capability import FactoryOperationRoutes
    from .combat_equipment_retained_lifecycle import _native_factory
    from .combat_stat_handler import NativeStatHandler

    runtime = _native_factory(factory)
    if (
        runtime is None
        or type(routes) is not FactoryOperationRoutes
        or routes.factory is not runtime
    ):
        return frozenset()
    route = routes.routes.get(40)
    registry = runtime.characteristic_registry.get(
        "effects", runtime.characteristic_registry
    )
    binding = registry.get("40")
    if (
        route is None
        or route.factory is not runtime
        or route.handler_type is not NativeStatHandler
        or not hasattr(binding, "get")
        or binding.get("runner") != "eWR"
        or binding.get("fixed_stat_id") is not None
    ):
        return frozenset()
    adapter = getattr(runtime.contexts.healing_events, "__self__", None)
    if not callable(runtime.contexts.stat) or runtime.contexts.stat is not getattr(
        getattr(adapter, "cast", None), "stat", None
    ):
        return frozenset()
    return frozenset(DYNAMIC_CURRENT_LOSS_EVENTS.values())
