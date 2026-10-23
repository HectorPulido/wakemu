"""Typed pre-pin descriptions of existing non-eWQ native leaf handlers.

No arithmetic here supplies actor stats, RNG, recipients or a running value.
Those operands remain owned by the existing transaction handlers.
"""
from collections.abc import Mapping


SET_CURRENT = frozenset((560, 561, 562, 563, 566))
FAMILIES = frozenset((48, 55, 303, 986, 1013)) | SET_CURRENT
OPERATION_IDS = {
    48: "resource.loss",
    55: "resource.loss",
    303: "spatial.orientation",
    986: "resource.maximum_percentage",
    1013: "resource.armor",
    **dict.fromkeys(SET_CURRENT, "resource.set_current"),
}


def parse(effect, profile):
    family = effect.get("effect_class")
    if family not in FAMILIES:
        return None, (), (), "No native primitive leaf adapter"
    values = tuple(profile["parameters"])
    flags = effect.get("native_effect_flags")
    if (
        not isinstance(flags, (list, tuple))
        or any(type(flag) is not int for flag in flags)
        or len(set(flags)) != len(flags)
    ):
        raise ValueError("Invalid native primitive flags")
    requirements = ["native_existing_primitive_execution", "native_runner_lifecycle"]
    dependencies = ()
    if family in (48, 55):
        if not values or set(flags) - {1, 3, 4, 5, 6, 14, 15, 16, 17, 19, 26, 30}:
            raise ValueError("Unsupported native eVZ amount or flags")
        parsed = dict(stat_id=2 if family == 55 else 3, requested=values[0])
        if values[0] == -1:
            requirements.append("native_trigger_context")
        if 19 not in flags:
            # Actual loss*10 selects this secondary state's level. A sampled
            # level would not prove the complete invocation-dependent graph.
            requirements.append("native_resource_loss_secondary_level_domain")
    elif family == 986:
        if len(values) not in (1, 3):
            raise ValueError("Native eZI requires one or three parameter pairs")
        parsed = dict(
            amount=values[0],
            apply_current=len(values) == 1 or values[1] == 1,
            restore_current=len(values) == 3 and values[2] == 1,
        )
    elif family == 1013:
        if not values or len(values) > 3:
            raise ValueError("Unsupported native armor parameter shape")
        mode = values[1] if len(values) > 1 else 3
        if mode not in range(4) or set(flags) - {3, 4, 5, 6, 17, 22, 23, 24, 29}:
            raise ValueError("Unsupported native armor mode or flags")
        element = ((values[2] + 128) % 256) - 128 if len(values) > 2 else None
        if element is not None and element not in range(7):
            raise ValueError("Unknown native armor elemental enum")
        parsed = dict(amount=values[0], mode=mode, element=element)
    elif family == 303:
        if not values:
            raise ValueError("Native orientation requires parameter zero")
        parsed = dict(mode=values[0])
    else:
        from .combat_set_current_characteristic import set_current_registry

        row = set_current_registry().get(str(family))
        if (
            not isinstance(row, Mapping)
            or row.get("runner") != "eWX"
            or row.get("numeric_kind") != 0
            or type(row.get("fixed_stat_id")) is not int
        ):
            raise ValueError("Missing native fixed numeric eWX registry")
        parsed = dict(
            stat_id=row["fixed_stat_id"],
            requested=values[0] if values else None,
            copy_caster_current=not values,
        )
    return parsed, tuple(requirements), dependencies, None


def context_capability(factory, routes, effect, detail):
    """Prove the real configured handler and ordinary retained transaction."""
    from .combat_armor import NativeArmorHandler
    from .combat_maximum_resource import NativePercentageHPHandler
    from .combat_orientation_effect import NativeOrientationHandler
    from .combat_resource_loss_handler import NativeResourceLossHandler
    from .combat_set_current_characteristic import NativeSetCurrentCharacteristicHandler
    from .combat_equipment_retained_lifecycle import preflight

    family = effect.get("effect_class")
    expected = (
        {
            48: NativeResourceLossHandler,
            55: NativeResourceLossHandler,
            303: NativeOrientationHandler,
            986: NativePercentageHPHandler,
            1013: NativeArmorHandler,
            **dict.fromkeys(SET_CURRENT, NativeSetCurrentCharacteristicHandler),
        }
    ).get(family)
    route = routes.routes.get(family)
    if expected is None or route is None or route.handler_type is not expected:
        return False
    if not isinstance(detail, Mapping) or not preflight(
        factory, detail.get("retained_container")
    ):
        return None
    if not callable(getattr(factory.contexts, "stat", None)):
        return None
    if family in (48, 55, 1013) and not callable(
        getattr(factory.contexts, "rounding", None)
    ):
        return None
    if family in (303, 1013) and factory.displacement_authority is None:
        return None
    return True
