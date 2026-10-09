"""eJz percentage arithmetic: float32 division and exact GS.B Java int floor."""
import math
import struct


def _float(value):
    return struct.unpack(">f", struct.pack(">f", value))[0]


def characteristic_percentage(current, maximum):
    if any(
        type(value) is not int or not -(1 << 31) <= value < (1 << 31)
        for value in (current, maximum)
    ):
        raise ValueError("Missing native signed characteristic percentage values")
    numerator, denominator = _float(current), _float(maximum)
    quotient = (
        numerator / denominator
        if denominator
        else math.nan
        if numerator == 0
        else math.copysign(math.inf, numerator)
    )
    value = _float(_float(quotient) * _float(100))
    # GS.B first performs saturating f2i, then decrements negative/nonfinite
    # nonintegral values. fcmpl treats NaN as -1; subtraction wraps Java int.
    integer = (
        0
        if math.isnan(value)
        else 2147483647
        if value >= 2147483647
        else -2147483648
        if value <= -2147483648
        else math.trunc(value)
    )
    if value >= 0:
        return float(integer)
    if _float(integer) != value:
        integer = ((integer - 1 + (1 << 31)) % (1 << 32)) - (1 << 31)
    return float(integer)
