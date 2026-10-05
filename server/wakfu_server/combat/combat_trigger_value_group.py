"""eYB1103: eVt.SQ from the actual triggering eZR, independent of SP."""
import math
from .combat_parameters import _float32, _integer
from .combat_level_group import _native_float_parameter
from .combat_value_transfer import transfer_value_context


def trigger_value_context(effect, invocation, context):
    if effect["effect_class"] != 1103:
        raise ValueError("Wrong native triggering-value group family")
    count = len(effect["parameters"]) // 2
    if not 1 <= count <= 8:
        raise ValueError("Unknown native eYB parameter variant")
    if not hasattr(invocation, "native_trigger_context"):
        raise ValueError("Missing audited native triggering source snapshot")
    source = invocation.native_trigger_context
    if source is None:
        # eYB.d(null) returns eYg.d unchanged, not SQ(0).
        return context
    if not isinstance(source, dict) or type(source.get("value")) is not int:
        raise ValueError("Missing authoritative triggering eZR.getValue")
    value = source["value"]
    if not -(1 << 31) <= value < (1 << 31):
        raise ValueError("Native triggering value must be signed int")
    ratio = (
        100.0
        if count <= 6
        else _native_float_parameter(effect["parameters"], 6, invocation.level)
    )
    addition = (
        0.0
        if count <= 7
        else _native_float_parameter(effect["parameters"], 7, invocation.level)
    )
    product = _float32(_float32(value) * ratio)
    quotient = _float32(product / 100.0)
    result = _float32(quotient + addition)
    result = _integer(math.trunc(result) if math.isfinite(result) else result)
    return transfer_value_context(context, result)
