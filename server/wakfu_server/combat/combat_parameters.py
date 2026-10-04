"""Native eVE.w/a(..., rpA) arithmetic, shared by spells and state effects.

Java uses float32 at each operation and snaps the growth term near integers
before adding the base. Python double arithmetic alone gives different damage.
"""
import math
import struct


def _float32(value):
    try:
        return struct.unpack(">f", struct.pack(">f", value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)


def _integer(value):
    if math.isnan(value):
        return 0
    return min(2147483647, max(-2147483648, value))


def parameter_value(parameters, index, level):
    if type(level) is not int or not -32768 <= level <= 32767:
        raise ValueError("Effect level must be a native signed short")
    if type(index) is not int or index < 0 or 2 * index + 1 >= len(parameters):
        raise ValueError("Unknown native effect parameter")
    base, growth = map(_float32, parameters[2 * index : 2 * index + 2])
    increment = _float32(growth * level)
    rounded = (
        _integer(math.floor(increment + 0.5))
        if math.isfinite(increment)
        else _integer(increment)
    )
    if abs(_float32(increment - rounded)) < 1e-5:
        increment = _float32(rounded)
    value = _float32(base + increment)
    if not math.isfinite(value):
        return _integer(value)
    return _integer(math.floor(value) if growth >= 0 else math.ceil(value))
