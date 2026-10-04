"""Native1047/eYs: eYg children leveled from HP plus VIRTUAL_HP.

The underlying eYn characteristic parameter6 is ignored by eYs's final
calculation. Actor resources must be a complete authoritative PA snapshot.
"""
from dataclasses import replace
import math
from .combat_parameters import parameter_value, _float32, _integer
from .combat_level_group import _native_float_parameter
from .combat_effect_groups import decode_group_mode, execute_ordered_group
from .combat_native_timing_context import native_definition_timing


def _i32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def _idiv(value, divisor):
    if divisor == 0:
        raise ValueError("Native HP group divides by zero maximum")
    return _i32(
        (abs(value) // abs(divisor)) * (-1 if (value < 0) != (divisor < 0) else 1)
    )


def hp_group_override(
    effect,
    level,
    *,
    current_hp,
    maximum_hp,
    current_virtual_hp,
    maximum_virtual_hp,
    return_native_override=False
):
    if effect["effect_class"] != 1047:
        raise ValueError("Wrong native HP group family")
    raw = effect["parameters"]
    count = len(raw) // 2
    if count not in (9, 10, 11, 12):
        raise ValueError("Unknown native1047 parameter variant")
    amounts = (current_hp, maximum_hp, current_virtual_hp, maximum_virtual_hp)
    if any(type(v) is not int or not -(1 << 31) <= v < (1 << 31) for v in amounts):
        raise ValueError("Missing authoritative native HP/VIRTUAL_HP snapshot")
    current = _i32(current_hp + current_virtual_hp)
    maximum = _i32(maximum_hp + maximum_virtual_hp)
    return _value_group_override(
        effect,
        level,
        current=current,
        maximum=maximum,
        return_native_override=return_native_override,
    )


def _value_group_override(
    effect, level, *, current, maximum, return_native_override=False
):
    raw = effect["parameters"]
    count = len(raw) // 2
    if count not in (9, 10, 11, 12):
        raise ValueError("Unknown native characteristic-group parameter variant")
    mode = parameter_value(raw, 10, level) if count >= 11 else 0
    if mode == 1:
        value = maximum
    elif mode == 2:
        value = _idiv(_i32(current * 100), maximum)
    elif mode == 3:
        value = _idiv(_i32(_i32(maximum - current) * 100), maximum)
    elif mode == 4:
        value = _i32(maximum - current)
    else:
        value = current
    if count == 9:
        divisor = parameter_value(raw, 8, level)
        amount = (
            value if divisor == 0 else _float32(_float32(value) / _float32(divisor))
        )
        override = (
            value
            if divisor == 0
            else _integer(math.floor(amount) if math.isfinite(amount) else amount)
        )
    else:
        base = _native_float_parameter(raw, 8, level)
        growth = _native_float_parameter(raw, 9, level)
        amount = _float32(base + _float32(growth * _float32(value)))
        rounding = parameter_value(raw, 11, level) if count >= 12 else 1
        if not math.isfinite(amount):
            override = _integer(amount)
        elif rounding == 2:
            override = _integer(math.floor(amount))
        elif rounding == 3:
            override = _integer(math.ceil(amount))
        else:
            override = _integer(math.floor(amount + 0.5))
    if return_native_override:
        return override
    return level if override == -1 else ((override + 32768) % 65536) - 32768


def runtime_group_level(
    effect, values, invocation, actors, *, return_native_override=False
):
    native_definition_timing(effect, invocation.level)
    mode = decode_group_mode(
        values["parameters"][:6], raw_target_parameter=effect["parameters"][4]
    )
    caster, target = invocation.caster_id, invocation.target_id
    if mode.actor_rebind == 1:
        caster = target
    elif mode.actor_rebind == 2:
        caster, target = target, caster
    identity = caster if values["parameters"][7] == 1 else target
    if identity is None:
        return (
            -1 if return_native_override else invocation.level
        )  # Native eYs.d null actor preserves override sentinel.
    actor = actors.get(identity)
    if actor is None:
        raise ValueError("Missing native HP group actor")
    current, maximum = actor.effect_stats, actor.effect_maxima
    if (
        not isinstance(current, dict)
        or not isinstance(maximum, dict)
        or any(k not in current or k not in maximum for k in (1, 92))
    ):
        raise ValueError("Missing complete HP and VIRTUAL_HP PA snapshot")
    return hp_group_override(
        effect,
        invocation.level,
        current_hp=current[1],
        maximum_hp=maximum[1],
        current_virtual_hp=current[92],
        maximum_virtual_hp=maximum[92],
        return_native_override=return_native_override,
    )


class NativeHPLevelGroupHandler:
    def __init__(self, fight, *, execute_child, group_cells, actor_position):
        self.fight, self.execute_child, self.group_cells, self.actor_position = (
            fight,
            execute_child,
            group_cells,
            actor_position,
        )

    def __call__(self, effect, values, invocation):
        level = runtime_group_level(effect, values, invocation, self.fight.actors)
        mode = decode_group_mode(
            values["parameters"][:6], raw_target_parameter=effect["parameters"][4]
        )
        outcomes = []

        def execute(child):
            result = self.execute_child(
                replace(
                    invocation,
                    reference=child.child_id,
                    level=level,
                    caster_id=child.caster_id,
                    target_id=child.target_id,
                    cell=child.cell,
                )
            )
            if type(result) is not bool:
                raise ValueError("Child must report native success")
            outcomes.append(result)
            return result

        execute_ordered_group(
            mode,
            effect["children"],
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            target_cell=invocation.cell,
            execute_child=execute,
            cell_targets=None
            if mode.on_target
            else self.group_cells(effect, invocation),
            caster_cell=self.actor_position(invocation.caster_id),
        )
        return any(outcomes)
