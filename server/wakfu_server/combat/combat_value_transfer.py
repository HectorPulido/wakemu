"""Native eYy865 arithmetic; source values must come from eYz callbacks."""
import math
from dataclasses import dataclass
from .combat_parameters import _float32


def transferred_value(value, percent, minimum, rounding, *, probability):
    for number in (value, percent, minimum, rounding):
        if type(number) is not int or not -(1 << 31) <= number < (1 << 31):
            raise ValueError("Native signed-int transfer parameters required")
    product = ((value * percent + (1 << 31)) % (1 << 32)) - (1 << 31)
    scaled = _float32(_float32(product) / _float32(100))
    if rounding == -1:
        result = math.floor(scaled)
    elif rounding == 1:
        result = math.ceil(scaled)
    else:
        # UP.bt uses GT.l(fraction), not round-to-nearest or truncation.
        if not callable(probability):
            raise ValueError("Native stochastic transfer RNG required")
        floor = math.floor(scaled)
        up = probability(float(scaled) - floor)
        if type(up) is not bool:
            raise ValueError("Native probability callback must return bool")
        result = floor + int(up)
    return max(result, minimum)


def capture_child_value(previous, running_value):
    """eYz.h keeps previous on zero; never infer value from success/HP."""
    if any(
        type(x) is not int or not -(1 << 31) <= x < (1 << 31)
        for x in (previous, running_value)
    ):
        raise ValueError("Actual native child runner value required")
    return running_value if running_value else previous


@dataclass(frozen=True)
class ValueTransferSpecification:
    percent: int = 100
    minimum: int = 0
    on_original_target: bool = False
    rounding: int = 0


def value_transfer_specification(parameters):
    """eYy.C reads the first four evaluated parameters; extras are ignored."""
    if not isinstance(parameters, (tuple, list)):
        raise ValueError("Evaluated native transfer parameters required")
    values = parameters[:4]
    if any(
        type(value) is not int or not -(1 << 31) <= value < (1 << 31)
        for value in values
    ):
        raise ValueError("Evaluated signed native transfer parameters required")
    return ValueTransferSpecification(
        percent=values[0] if values else 100,
        minimum=values[1] if len(values) > 1 else 0,
        on_original_target=len(values) > 2 and values[2] != 0,
        rounding=values[3] if len(values) > 3 else 0,
    )


def execute_value_transfer(
    specification, *, execute_first, execute_second, probability, skip_second
):
    """Ordered eYy calls; first receives the actual eYz.h value observer.

    Callers supply the native child context/level and original coordinates.
    The first child's boolean result is deliberately ignored: only its runner
    callback can populate the accumulator. skip_second is the authoritative
    faO/101395 exception, resolved by the caller before entering this helper.
    """
    if not isinstance(specification, ValueTransferSpecification):
        raise ValueError("Native transfer specification required")
    if (
        type(specification.on_original_target) is not bool
        or type(skip_second) is not bool
        or not callable(execute_first)
        or not callable(execute_second)
    ):
        raise ValueError("Native transfer child execution authority required")
    for value in (specification.percent, specification.minimum, specification.rounding):
        if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
            raise ValueError("Native signed transfer parameter required")
    accumulated = 0
    observing = True

    def capture(value):
        nonlocal accumulated
        if not observing:
            raise ValueError("Transfer child callback escaped its execution")
        accumulated = capture_child_value(accumulated, value)

    try:
        execute_first(capture)
    finally:
        observing = False
    if accumulated == 0 or skip_second:
        return False
    value = transferred_value(
        accumulated,
        specification.percent,
        specification.minimum,
        specification.rounding,
        probability=probability,
    )
    result = execute_second(value, specification.on_original_target)
    if type(result) is not bool:
        raise ValueError("Transfer child must report native application success")
    return result


def transfer_value_context(payload, value):
    """Actual eVt.mb(false)+SQ(value): fields5/6/9, preserve SP field4."""
    from wakfu_server.wire import proto_fields
    from .combat_effects import _integer, _varint

    if (
        not isinstance(payload, bytes)
        or type(value) is not int
        or not -(1 << 31) <= value < (1 << 31)
    ):
        raise ValueError("Native context bytes and signed transfer value required")
    fields = []
    seen = set()
    for tag, item in proto_fields(payload):
        field, wire = tag >> 3, tag & 7
        if field in seen:
            raise ValueError("Duplicate native context field")
        seen.add(field)
        if field in (5, 6, 9):
            if wire != 0:
                raise ValueError("Invalid native transfer context wire")
            continue
        if wire == 0:
            fields.append(_varint(tag) + _varint(item))
        elif wire == 2:
            fields.append(_varint(tag) + _varint(len(item)) + item)
        else:
            raise ValueError("Unsupported native context wire")
    return b"".join(fields) + _integer(5, 0) + _integer(6, value) + _integer(9, 1)


def apply_context_value(calculated, payload):
    """eZR.n -> a(eVt), AFTER C; a missing context leaves value unchanged."""
    from wakfu_server.wire import proto_fields

    if type(calculated) is not int or not -(1 << 31) <= calculated < (1 << 31):
        raise ValueError("Actual signed native calculated runner value required")
    if payload is None:
        return calculated
    if not isinstance(payload, bytes):
        raise ValueError("Native context bytes required")
    values = {}
    for tag, value in proto_fields(payload):
        field, wire = tag >> 3, tag & 7
        if field in values:
            raise ValueError("Duplicate native forced-value context")
        values[field] = (wire, value)
    kind = values.get(9, (0, 0))
    if kind[0] != 0 or kind[1] not in (0, 1, 2):
        raise ValueError("Unknown native eVu forced-value type")
    if kind[1] == 0:
        return calculated
    wire, forced = values.get(6, (0, 0))
    if wire != 0:
        raise ValueError("Invalid native forced-value wire")
    forced = ((forced + (1 << 31)) % (1 << 32)) - (1 << 31)
    if kind[1] == 1:
        return forced
    product = ((calculated * forced + (1 << 31)) % (1 << 32)) - (1 << 31)
    # JVM idiv truncates toward zero, unlike Python // for negative values.
    quotient = abs(product) // 100
    return max(-quotient if product < 0 else quotient, 1)
