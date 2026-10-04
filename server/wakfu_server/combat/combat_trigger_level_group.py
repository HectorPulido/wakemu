"""Native1020/eYw child level from the actual triggering eZR.getValue.

Absence of a source is distinct from an unknown snapshot. This module never
fabricates lifecycle events or treats a source's cost/HP as its effect value.
"""
import math
from .combat_parameters import _float32, _integer
from .combat_level_group import _native_float_parameter
from .combat_native_timing_context import native_definition_timing


def trigger_group_override(
    effect, level, *, source_present, trigger_value, return_native_override=False
):
    if effect["effect_class"] != 1020:
        raise ValueError("Wrong native trigger-value group family")
    if type(level) is not int or not -32768 <= level <= 32767:
        raise ValueError("Native group level must be signed short")
    count = len(effect["parameters"]) // 2
    if not 1 <= count <= 7:
        raise ValueError("Unknown native1020 parameter variant")
    if type(source_present) is not bool:
        raise ValueError("Explicit native triggering source presence required")
    if not source_present:
        if trigger_value is not None:
            raise ValueError("Absent native source cannot supply an effect value")
        override = -1  # eYw.d null source returns the unchanged parent context.
    else:
        if type(trigger_value) is not int or not -(1 << 31) <= trigger_value < (
            1 << 31
        ):
            raise ValueError("Missing authoritative triggering eZR.getValue")
        ratio = (
            1.0
            if count <= 6
            else _native_float_parameter(effect["parameters"], 6, level)
        )
        product = _float32(_float32(trigger_value) * ratio)
        # f2i truncates toward zero, saturates infinity and maps NaN to0.
        override = _integer(math.trunc(product) if math.isfinite(product) else product)
    if return_native_override:
        return override
    return level if override == -1 else ((override + 32768) % 65536) - 32768


def runtime_group_level(
    effect, values, invocation, actors, *, return_native_override=False
):
    native_definition_timing(effect, invocation.level)
    if not hasattr(invocation, "native_trigger_context"):
        raise ValueError("Missing audited native triggering source snapshot")
    source = invocation.native_trigger_context
    if source is None:
        source_present, trigger_value = False, None
    elif isinstance(source, dict) and "value" in source:
        source_present, trigger_value = True, source["value"]
    else:
        raise ValueError("Missing authoritative triggering eZR.getValue")
    return trigger_group_override(
        effect,
        invocation.level,
        source_present=source_present,
        trigger_value=trigger_value,
        return_native_override=return_native_override,
    )
