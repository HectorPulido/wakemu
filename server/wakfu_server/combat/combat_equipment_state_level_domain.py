"""Compact native304 requested-level proofs, including signed-short wrapping.

The proof describes inputs to the ordinary state applicator. It does not
replace execution, clamp a negative carrier to zero, or skip its lifetime.
"""
from collections.abc import Mapping
import math

from .combat_equipment_dynamic_levels import UnknownDynamicLevel


def state_level_witnesses(effect, levels, states, effects):
    """Return actual input witnesses for every reachable carrier branch.

    Nonnegative carrier levels retain every reachable native clamped grade.
    A wrapped negative interval is equivalent for descendant admission only
    when every original state child excludes negative levels. The carrier
    itself still requires the separately qualified signed-state lifecycle.
    """
    from .combat_parameters import _float32, parameter_value

    raw = effect.get("parameters")
    if (
        effect.get("effect_class") != 304
        or effect.get("parameter_count") != 3
        or not isinstance(raw, (tuple, list))
        or len(raw) != 6
        or raw[1] != 0
        or raw[5] != 0
        or not levels
    ):
        raise UnknownDynamicLevel("Missing invariant native state application shape")
    low, high = levels.start, levels.stop - 1
    state_id = ((parameter_value(raw, 0, low) + 32768) % 65536) - 32768
    state = states.get(str(state_id))
    maximum = state.get("maximum_level") if isinstance(state, Mapping) else None
    if state_id <= 0 or type(maximum) is not int or not 0 <= maximum <= 32767:
        raise UnknownDynamicLevel("Missing native applied-state level clamp")
    base, growth = _float32(raw[2]), _float32(raw[3])
    if not math.isfinite(base) or not math.isfinite(growth):
        raise UnknownDynamicLevel("Non-finite native state-level parameters")
    for endpoint in (low, high):
        product = _float32(growth * endpoint)
        if not math.isfinite(product) or not math.isfinite(_float32(base + product)):
            raise UnknownDynamicLevel("Native state-level interval overflows float32")

    # Reverse a decreasing expression so every binary search is monotone.
    first_input = low if growth >= 0 else high
    step = 1 if growth >= 0 else -1
    count = high - low + 1

    def value(index):
        return parameter_value(raw, 1, first_input + step * index)

    minimum_raw, maximum_raw = value(0), value(count - 1)
    first_period = (minimum_raw + 32768) // 65536
    last_period = (maximum_raw + 32768) // 65536
    # A compact proof is intentional. Wide float32 jumps can skip many short
    # periods; those shapes need a separate modular reachability proof.
    if last_period - first_period > 32:
        raise UnknownDynamicLevel(
            "Native state wrapping needs a modular reachability proof"
        )

    negative_possible = any(
        max(minimum_raw, period * 65536 - 32768) <= min(maximum_raw, period * 65536 - 1)
        for period in range(first_period, last_period + 1)
    )
    if negative_possible:
        children = state.get("effect_ids")
        if not isinstance(children, (tuple, list)):
            raise UnknownDynamicLevel("Missing signed-state child definitions")
        for reference in children:
            child = effects.get(str(reference))
            if (
                not isinstance(child, Mapping)
                or type(child.get("minimum_level")) is not int
                or child["minimum_level"] < 0
            ):
                raise UnknownDynamicLevel(
                    "Negative state descendants need a complete domain proof"
                )

    seen = {low, high}

    def boundary(target):
        if target < minimum_raw or target > maximum_raw:
            return
        left, right = 0, count - 1
        while left < right:
            middle = (left + right) // 2
            if value(middle) < target:
                left = middle + 1
            else:
                right = middle
        seen.add(first_input + step * left)
        if left:
            seen.add(first_input + step * (left - 1))

    for period in range(first_period, last_period + 1):
        origin = period * 65536
        for grade in range(maximum + 1):
            boundary(origin + grade)
        # Retain both sides of signed wrapping and negative/zero transitions.
        for offset in (-32768, -1, 0, 32767, 32768):
            boundary(origin + offset)
    return tuple(sorted(seen))
