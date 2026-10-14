"""Native1101/eYq: polynomial group level with Java arithmetic.

Child dispatch, target selection and subscriptions use the existing eYg
implementation. Only the inherited eVt.SP level override is calculated here.
"""
import math

from .combat_parameters import _float32, _integer
from .combat_state_level_group import float_parameter


def native_override(effect, values, invocation):
    if effect.get("effect_class") != 1101:
        raise ValueError("Wrong native polynomial group family")
    count = effect.get("parameter_count")
    raw = effect.get("parameters")
    if (
        type(count) is not int
        or not 2 <= count <= 8
        or not isinstance(raw, (list, tuple))
        or len(raw) != count * 2
        or len(values["parameters"]) != count
    ):
        raise ValueError("Unknown native1101 polynomial parameter variant")
    level = invocation.level
    if type(level) is not int or not -32768 <= level <= 32767:
        raise ValueError("Polynomial level must be a native signed short")
    amount = _float32(0)
    power = 1
    for index in range(count):
        coefficient = float_parameter(raw, index, level)
        amount = _float32(amount + _float32(coefficient * _float32(power)))
        power = ((power * level + (1 << 31)) % (1 << 32)) - (1 << 31)
    return int(_integer(math.floor(amount + 0.5) if math.isfinite(amount) else amount))


def runtime_child_level(effect, values, invocation, *, return_native_override=False):
    override = native_override(effect, values, invocation)
    if return_native_override:
        return override
    return invocation.level if override == -1 else ((override + 32768) % 65536) - 32768
