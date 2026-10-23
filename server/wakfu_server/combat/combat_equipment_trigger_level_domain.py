"""Conservative native1020 child-domain proofs without enumerating levels.

Native eYw always yields a signed-short child level, including its absent-Qe
parent-level path. Only leaf operations whose parameter branches are invariant
across that entire domain can be statically described here. The normal typed
operation, criteria, target, timing and factory checks still validate witnesses.
"""
from collections.abc import Mapping
import math

from .combat_equipment_dynamic_levels import UnknownDynamicLevel


SHORT_DOMAIN = (-32768, 32767)


def trigger_group_mode(effect, level):
    from .combat_definitions import effect_profile
    from .combat_effect_groups import decode_group_mode
    from .combat_native_events import validate_group_registration_flags

    raw = effect.get("parameters")
    count = effect.get("parameter_count")
    if (
        effect.get("effect_class") != 1020
        or type(count) is not int
        or not 1 <= count <= 7
        or not isinstance(raw, (tuple, list))
        or len(raw) != 2 * count
        or any(
            type(value) not in (int, float) or not math.isfinite(value) for value in raw
        )
    ):
        raise ValueError("Invalid native1020 group parameters")
    flags = effect.get("native_effect_flags")
    if not isinstance(flags, (tuple, list)):
        raise UnknownDynamicLevel("Missing native trigger-group flag authority")
    validate_group_registration_flags(
        flags,
        active=False,
        constructor=True,
        effect=effect,
        reference=effect.get("_capability_reference"),
    )
    values = effect_profile(effect, level)["parameters"]
    return decode_group_mode(
        values[:6], raw_target_parameter=raw[4] if count >= 3 else None
    )


def leaf_domain_witnesses(effect, *, registry=None):
    """Return endpoint witnesses for a proved invariant leaf parameter shape.

    Only the amount pair may vary (p0 for damage/heal, p1 for430).
    Native mask/far/mode/replace fields and timing /
    probability branches are level-independent. Float32 parameter evaluation
    saturates to int32, so signed healing/trigger amounts remain valid across
    the short domain. Damage additionally requires nonnegative base/growth
    on a nonnegative admitted level interval. Native dispatcher range guards
    skip levels outside the descriptor interval before evaluating the leaf.
    """
    if not isinstance(effect, Mapping) or effect.get("children") not in ([], ()):
        raise UnknownDynamicLevel(
            "Dynamic descendants need a complete invariant leaf proof"
        )
    family = effect.get("effect_class")
    from .combat_damage_contracts import DAMAGE_FAMILIES, HEAL_ELEMENTS
    from .combat_maximum_resource import REDUCTION_FAMILIES

    rows = registry.get("effects", registry) if isinstance(registry, Mapping) else None
    row = rows.get(str(family)) if isinstance(rows, Mapping) else None
    current = isinstance(row, Mapping) and row.get("runner") in ("eWQ", "eWR")
    if (
        family
        not in (*DAMAGE_FAMILIES, *HEAL_ELEMENTS, *REDUCTION_FAMILIES, 400, 430, 1013)
        and not current
    ):
        raise UnknownDynamicLevel(
            "No invariant native parameter-domain adapter for leaf family"
        )
    low, high = effect.get("minimum_level"), effect.get("maximum_level")
    if type(low) is not int or type(high) is not int or low > high:
        raise ValueError("Invalid native leaf level interval")
    low, high = max(low, SHORT_DOMAIN[0]), min(high, SHORT_DOMAIN[1])
    if low > high:
        return ()
    raw, count = effect.get("parameters"), effect.get("parameter_count")
    if (
        not isinstance(raw, (tuple, list))
        or type(count) is not int
        or len(raw) != 2 * count
        or any(
            type(value) not in (int, float) or not math.isfinite(value) for value in raw
        )
    ):
        raise ValueError("Malformed dynamic leaf parameter pairs")
    if (
        family in (*DAMAGE_FAMILIES, *HEAL_ELEMENTS, 1013)
        and count not in (1, 2, 3)
        or family in REDUCTION_FAMILIES
        and count not in (1, 2, 3, 4)
        or current
        and count not in (1, 2, 3)
        or family == 430
        and count < 3
    ):
        raise UnknownDynamicLevel("Unproved dynamic leaf parameter shape")
    amount_pair = 1 if family == 430 else 0
    if any(raw[2 * index + 1] != 0 for index in range(count) if index != amount_pair):
        raise UnknownDynamicLevel("Dynamic leaf selector/mode depends on child level")
    if family in DAMAGE_FAMILIES and (low < 0 or raw[0] < 0 or raw[1] < 0):
        raise UnknownDynamicLevel(
            "Dynamic damage sign needs an additional domain proof"
        )
    if family in DAMAGE_FAMILIES and count == 3 and raw[4] != 0:
        raise UnknownDynamicLevel(
            "Dynamic percent-HP damage needs a separate integer-overflow proof"
        )
    if (
        (current or family in REDUCTION_FAMILIES)
        and raw
        and raw[1] != 0
        and (low < 0 or raw[0] < 0 or raw[1] < 0)
    ):
        raise UnknownDynamicLevel(
            "Dynamic characteristic sentinel branches need an additional domain proof"
        )
    if effect.get("probability_per_level") != 0:
        raise UnknownDynamicLevel(
            "Dynamic probability needs an additional domain proof"
        )
    masks = effect.get("target_masks")
    if (
        not isinstance(masks, (tuple, list))
        or len(masks) != 7
        or any(mask for mask in masks)
    ):
        raise UnknownDynamicLevel(
            "Nested dynamic subscriptions need their own domain proof"
        )
    mode, timing = effect.get("native_execution_mode"), effect.get(
        "native_timing_definition"
    )
    if not isinstance(timing, Mapping):
        raise UnknownDynamicLevel("Missing native dynamic timing definition")
    if mode == 2 and effect.get("native_definition_class") in ("eVy", "eVI"):
        invariant = timing.get("ryF") == 0 and timing.get("ryI") == 0
    elif mode == 1 and effect.get("native_definition_class") == "eVH":
        invariant = timing.get("rzw") == 0
    else:
        invariant = mode == 0
    if not invariant:
        raise UnknownDynamicLevel(
            "Dynamic leaf timing needs an additional domain proof"
        )
    return tuple(dict.fromkeys((low, high)))


def child_domain_witnesses(effect, effects, *, registry=None):
    children = effect.get("children")
    if (
        not isinstance(children, (tuple, list))
        or not children
        or any(type(child) is not int or child <= 0 for child in children)
        or not isinstance(effects, Mapping)
    ):
        raise UnknownDynamicLevel("Missing complete native1020 child definitions")
    result = []
    for child in dict.fromkeys(children):
        definition = effects.get(str(child))
        if not isinstance(definition, Mapping):
            raise UnknownDynamicLevel("Missing compiled dynamic child definition")
        for level in leaf_domain_witnesses(definition, registry=registry):
            result.append((child, level))
    return tuple(result)
