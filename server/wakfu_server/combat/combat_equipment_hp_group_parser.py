"""Pure native eYs/1047 capability parsing for equipment-owned groups.

Execution remains in EffectDispatcher and combat_hp_level_group. HP plus
VIRTUAL_HP is resolved anew for each invocation. A preparation snapshot cannot
stand in for future HP, Java int overflow, native rounding or sentinel handling.
"""
from collections.abc import Mapping


def parse(effect, profile, level):
    """Describe the existing native runner and its complete output type domain.

    The signed-short domain deliberately includes overflow and inherited/null-PA
    paths. Callers must assess each reachable child level, intersected with that
    child's native level bounds, rather than claiming a guessed HP percentage
    range or using the item's level as a dynamic child level.
    """
    from wakfu_server.combat_effect_groups import decode_group_mode
    from wakfu_server.combat_level_group import _native_float_parameter
    from wakfu_server.combat_native_events import validate_group_registration_flags
    from wakfu_server.combat_parameters import parameter_value

    if not isinstance(effect, Mapping) or effect.get("effect_class") != 1047:
        raise ValueError("Wrong native HP group family")
    count = effect.get("parameter_count")
    raw = effect.get("parameters")
    if (
        type(count) is not int
        or count not in (9, 10, 11, 12)
        or not isinstance(raw, (tuple, list))
        or len(raw) != count * 2
        or type(level) is not int
        or not -32768 <= level <= 32767
    ):
        raise ValueError("Unknown native HP group parameter variant")
    values = profile.get("parameters")
    if (
        not isinstance(values, (tuple, list))
        or len(values) != count
        or any(type(value) is not int for value in values)
    ):
        raise ValueError("Missing native HP group evaluated parameters")
    mode = decode_group_mode(values[:6], raw_target_parameter=raw[4])
    flags = effect.get("native_effect_flags")
    if not isinstance(flags, (tuple, list)):
        raise ValueError("Missing native HP group registration flags")
    validate_group_registration_flags(
        flags,
        active=False,
        constructor=True,
        effect=effect,
        reference=effect.get("_capability_reference"),
    )
    # Use the runner's actual native parameter readers. The inherited PA key
    # is ignored by eYs when HP or VIRTUAL_HP exists, but matters on null-PA PVs.
    inherited_stat = parameter_value(raw, 6, level) & 255
    actor = "caster" if parameter_value(raw, 7, level) == 1 else "target"
    if count == 9:
        transform = dict(divisor=parameter_value(raw, 8, level))
    else:
        transform = dict(
            base=_native_float_parameter(raw, 8, level),
            growth=_native_float_parameter(raw, 9, level),
            rounding=parameter_value(raw, 11, level) if count == 12 else 1,
        )
    return dict(
        group_mode=mode,
        selected_actor=actor,
        inherited_stat=inherited_stat,
        value_mode=parameter_value(raw, 10, level) if count >= 11 else 0,
        transform=transform,
        child_level_domain=(-32768, 32767),
    )


def child_levels(parsed, child):
    """Match EffectDispatcher's native skipped_level guard before child work."""
    domain = parsed.get("child_level_domain")
    low, high = child.get("minimum_level"), child.get("maximum_level")
    if (
        domain != (-32768, 32767)
        or type(low) is not int
        or type(high) is not int
        or low > high
    ):
        raise ValueError("Missing native HP group child level bounds")
    return range(max(-32768, low), min(32767, high) + 1)


def _level_invariant_metadata(effect):
    from wakfu_server.combat_equipment_dynamic_levels import UnknownDynamicLevel

    if effect.get("children") not in ([], ()):
        raise UnknownDynamicLevel(
            "Dynamic nested groups require a complete child-domain proof"
        )
    if effect.get("probability_per_level") != 0:
        raise UnknownDynamicLevel("Dynamic child probability needs an interval proof")
    masks = effect.get("target_masks")
    if (
        not isinstance(masks, (tuple, list))
        or len(masks) != 7
        or any(mask for mask in masks)
    ):
        raise UnknownDynamicLevel(
            "Dynamic child subscriptions need a level-domain proof"
        )
    timing = effect.get("native_timing_definition")
    if not isinstance(timing, Mapping):
        raise UnknownDynamicLevel("Missing dynamic child timing authority")
    mode = effect.get("native_execution_mode")
    if mode == 2 and effect.get("native_definition_class") in ("eVy", "eVI"):
        invariant = timing.get("ryF") == 0 and timing.get("ryI") == 0
    elif mode == 1 and effect.get("native_definition_class") == "eVH":
        invariant = timing.get("rzw") == 0
    else:
        invariant = mode == 0
    if not invariant:
        raise UnknownDynamicLevel("Dynamic child timing needs an interval proof")


def child_domain_witnesses(effect, effects, states, *, registry=None):
    """Prove parameter-equivalent witnesses without scanning 65,536 levels.

    Constant leaf parameters need one witness. State application may vary only
    its requested level: native float32 evaluation is monotone on this finite
    interval, and state_profile clamps it to the definition maximum. Binary
    searches retain each reachable normalized state level and both endpoints.
    Native signed-short wrap is not guessed: an interval crossing it defers.
    Remaining amount-only leaf shapes reuse the existing shared interval proof.
    Every witness still requires the real typed parser and capability provider.
    """
    import math
    from wakfu_server.combat_equipment_dynamic_levels import UnknownDynamicLevel
    from wakfu_server.combat_parameters import parameter_value

    children = effect.get("children")
    if (
        not isinstance(children, (tuple, list))
        or not children
        or not isinstance(effects, Mapping)
        or not isinstance(states, Mapping)
    ):
        raise UnknownDynamicLevel("Missing complete native HP group child definitions")
    state_rows = states.get("states", states)
    if not isinstance(state_rows, Mapping):
        raise UnknownDynamicLevel("Missing native HP group state definitions")
    result = []
    for child in dict.fromkeys(children):
        if type(child) is not int or child <= 0:
            raise ValueError("Invalid native HP group child identity")
        definition = effects.get(str(child))
        if not isinstance(definition, Mapping):
            raise UnknownDynamicLevel("Missing compiled native HP group child")
        levels = child_levels({"child_level_domain": (-32768, 32767)}, definition)
        if not levels:
            continue
        _level_invariant_metadata(definition)
        raw, count = definition.get("parameters"), definition.get("parameter_count")
        if (
            not isinstance(raw, (tuple, list))
            or type(count) is not int
            or len(raw) != count * 2
            or any(
                type(value) not in (int, float) or not math.isfinite(value)
                for value in raw
            )
        ):
            raise ValueError("Malformed dynamic HP child parameter pairs")
        low, high = levels.start, levels.stop - 1
        varying = {index for index in range(count) if raw[2 * index + 1] != 0}
        if not varying:
            witnesses = (low,)
        elif definition.get("effect_class") == 304 and varying == {1} and count == 3:
            from wakfu_server.combat_parameters import _float32

            # A finite Python float may overflow when converted to the native
            # float32 type. Opposite infinities can produce interior NaN -> 0,
            # invalidating an endpoint/binary-search monotonicity argument.
            base, growth = _float32(raw[2]), _float32(raw[3])
            if not math.isfinite(base) or not math.isfinite(growth):
                raise UnknownDynamicLevel(
                    "Dynamic state level has non-finite native float32 parameters"
                )
            for endpoint in (low, high):
                increment = _float32(growth * endpoint)
                if not math.isfinite(increment) or not math.isfinite(
                    _float32(base + increment)
                ):
                    raise UnknownDynamicLevel(
                        "Dynamic state level overflows its native float32 interval"
                    )
            state_id = parameter_value(raw, 0, low)
            state_id = ((state_id + 32768) % 65536) - 32768
            state = state_rows.get(str(state_id))
            maximum = state.get("maximum_level") if isinstance(state, Mapping) else None
            if type(maximum) is not int or not 0 <= maximum <= 32767:
                raise UnknownDynamicLevel("Missing native applied-state level clamp")
            first, last = parameter_value(raw, 1, low), parameter_value(raw, 1, high)
            if min(first, last) < 0 or max(first, last) > 32767:
                raise UnknownDynamicLevel(
                    "Dynamic state level crosses its native signed-short domain"
                )
            ascending = raw[3] > 0
            start = low if ascending else high

            def value_at(index):
                actual = start + index if ascending else start - index
                return min(maximum, parameter_value(raw, 1, actual))

            seen = {low, high}
            # The normalized output interval is at most the actual state's
            # declared maximum, independent of the equipment input domain.
            for target in range(
                min(maximum, min(first, last)), min(maximum, max(first, last)) + 1
            ):
                left, right = 0, high - low
                while left < right:
                    middle = (left + right) // 2
                    if value_at(middle) < target:
                        left = middle + 1
                    else:
                        right = middle
                actual = start + left if ascending else start - left
                seen.add(actual)
            witnesses = tuple(sorted(seen))
        else:
            from wakfu_server.combat_equipment_trigger_level_domain import (
                leaf_domain_witnesses,
            )

            witnesses = leaf_domain_witnesses(definition, registry=registry)
        result.extend((child, level) for level in witnesses)
    return tuple(result)
