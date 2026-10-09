"""Original eHI constructor over live frm characteristic operands.

Fresh PA definitions and the class aKz curves are source-exported inputs.
The producer returns raw tB values; no source actor or retained stack is changed.
"""
import math
from .combat_parameters import _float32, _integer
from .combat_character_copy_codec import CopyCharacteristic


def _i32(value):
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def copy_characteristics(
    source_currents,
    source_maxima,
    *,
    fresh_definitions,
    breed_curves,
    level,
    percentage,
    maximum_caps,
    native_order
):
    if (
        not isinstance(source_currents, dict)
        or not isinstance(source_maxima, dict)
        or not isinstance(fresh_definitions, dict)
        or not isinstance(breed_curves, dict)
        or not isinstance(maximum_caps, dict)
        or type(level) is not int
        or not -32768 <= level <= 32767
        or type(percentage) is not int
        or not -(1 << 31) <= percentage < (1 << 31)
    ):
        raise ValueError("Missing native character-copy characteristic operands")
    keys = {int(key) for key in fresh_definitions}
    if (
        not isinstance(native_order, tuple)
        or len(native_order) != len(keys)
        or set(native_order) != keys
        or any(type(identity) is not int for identity in native_order)
    ):
        raise ValueError("Missing original copied ffh encounter order")
    if set(source_currents) != keys or set(source_maxima) != keys:
        raise ValueError("Incomplete actual frm character-copy source")
    values = {}
    bounds = {}
    for identity in keys:
        row = fresh_definitions[str(identity)]
        if (
            type(row.get("expandable")) is not bool
            or type(row.get("over_max_current")) is not bool
            or any(
                type(row.get(key)) is not int
                for key in (
                    "current",
                    "reset_minimum",
                    "reset_maximum",
                    "percentage",
                    "hard_minimum",
                    "hard_maximum",
                )
            )
            or row["percentage"] != 0
            or any(
                type(v) is not int or not -(1 << 31) <= v < (1 << 31)
                for v in (source_currents[identity], source_maxima[identity])
            )
        ):
            raise ValueError("Unverified fresh copied PA definition")
        values[identity] = [
            row["current"],
            row["reset_minimum"],
            max(row["reset_minimum"], row["reset_maximum"]),
            0,
        ]
        bounds[identity] = [row["hard_minimum"], row["hard_maximum"]]

    def effective_max(identity):
        low, high = bounds[identity]
        return max(low, min(high, values[identity][2]))

    def set_current(identity, amount):
        low = max(bounds[identity][0], min(bounds[identity][1], values[identity][1]))
        high = (
            bounds[identity][1]
            if fresh_definitions[str(identity)]["over_max_current"]
            else effective_max(identity)
        )
        values[identity][0] = max(low, min(high, amount))

    def set_maximum(identity, amount):
        values[identity][2] = max(values[identity][1], amount)
        if (
            values[identity][0] > effective_max(identity)
            and not fresh_definitions[str(identity)]["over_max_current"]
        ):
            set_current(identity, effective_max(identity))

    for identity in keys:
        if fresh_definitions[str(identity)]["expandable"]:
            set_maximum(identity, source_maxima[identity])
        else:
            set_current(identity, source_currents[identity])
    for key, coefficient in breed_curves.items():
        identity = int(key)
        if identity not in keys or type(coefficient) not in (int, float):
            raise ValueError("Unknown native eGU class curve")
        product = _float32(_float32(level) * _float32(coefficient))
        delta = (
            _integer(math.floor(product))
            if math.isfinite(product)
            else _integer(product)
        )
        if values[identity][2] != (1 << 31) - 1:
            set_maximum(identity, _i32(values[identity][2] + delta))
        before = values[identity][0]
        room = effective_max(identity) - before
        set_current(
            identity, effective_max(identity) if delta > room else _i32(before + delta)
        )
    for identity in (2, 3):
        set_current(identity, effective_max(identity))
    set_current(4, source_currents[4])
    set_maximum(14, 0)  # ffw.sgM KO_TIME_BEFORE_DEATH.
    for identity, cap in maximum_caps.items():
        if identity not in keys or type(cap) is not int:
            raise ValueError("Unknown native eGK maximum bound")
        bounds[identity][1] = max(bounds[identity][0], cap)
    ratio = _float32(_float32(percentage) / 100.0)
    if ratio != 1.0:
        for identity in keys - {2, 3, 4}:
            amount = (
                effective_max(identity)
                if fresh_definitions[str(identity)]["expandable"]
                else max(
                    bounds[identity][0],
                    min(effective_max(identity), values[identity][0]),
                )
            )
            scaled = amount * ratio
            result = (
                _integer(math.ceil(scaled))
                if math.isfinite(scaled)
                else _integer(scaled)
            )
            if fresh_definitions[str(identity)]["expandable"]:
                set_maximum(identity, result)
            else:
                set_current(identity, result)
    set_current(1, source_currents[1])
    scaled_hp = source_maxima[1] * ratio
    set_maximum(
        1,
        _integer(math.trunc(scaled_hp))
        if math.isfinite(scaled_hp)
        else int(_integer(scaled_hp)),
    )
    return tuple(
        CopyCharacteristic(identity, *values[identity]) for identity in native_order
    )
