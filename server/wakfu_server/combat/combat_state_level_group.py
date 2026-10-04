"""Native844/eYr child-group level derived from first matching running state.

Group330 semantics remain shared; relative probability is still unsupported.
No state lookup from a class/spell fixture or maximum/summed level is used.
"""
import math
from dataclasses import replace
from .combat_parameters import _float32, _integer
from .combat_effect_groups import decode_group_mode, execute_ordered_group
from .combat_effect_dispatch import UnsupportedEffectExecution


def float_parameter(raw, index, level):
    base, growth = map(_float32, raw[index * 2 : index * 2 + 2])
    increment = _float32(growth * level)
    rounded = (
        _integer(math.floor(increment + 0.5))
        if math.isfinite(increment)
        else _integer(increment)
    )
    if abs(_float32(increment - rounded)) < 1e-5:
        increment = _float32(rounded)
    return _float32(base + increment)


def child_level(effect, values, invocation, actors, *, return_native_override=False):
    parameters = values["parameters"]
    count = len(parameters)
    if not 7 <= count <= 10:
        raise UnsupportedEffectExecution("Unknown844 parameter variant")
    caster, target = invocation.caster_id, invocation.target_id
    rebind = ((parameters[5] + 128) % 256) - 128
    if rebind == 1:
        caster = target
    elif rebind == 2:
        caster, target = target, caster
    actor_id = caster if count >= 8 and parameters[7] == 1 else target
    actor = actors.get(actor_id)
    if actor is None:
        return (
            -1 if return_native_override else invocation.level
        )  # Native null actor returns base eVt immediately.
    factor = (
        float_parameter(effect["parameters"], 8, invocation.level)
        if count >= 9
        else 1.0
    )
    constant = _float32(parameters[9]) if count >= 10 else 0.0
    entry = next(
        (e for e in actor.state_ledger.entries if e.reference == parameters[6]), None
    )
    if entry is None:
        result = (
            _integer(math.floor(constant))
            if count >= 10
            else (-1 if return_native_override else invocation.level)
        )
    else:
        amount = _float32(constant + _float32(factor * entry.level))
        result = (
            _integer(math.floor(amount)) if math.isfinite(amount) else _integer(amount)
        )
    # eVt.SP(-1) is the no-level-override sentinel.
    if return_native_override:
        return result
    if result == -1:
        return invocation.level
    return ((result + 32768) % 65536) - 32768


class NativeStateLevelGroupHandler:
    def __init__(self, fight, *, execute_child, group_cells, actor_position):
        self.fight = fight
        self.execute_child = execute_child
        self.group_cells = group_cells
        self.actor_position = actor_position

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 844:
            raise UnsupportedEffectExecution("Unsupported state-level group")
        mode = decode_group_mode(
            values["parameters"][:6], raw_target_parameter=effect["parameters"][4]
        )
        level = child_level(effect, values, invocation, self.fight.actors)
        results = []

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
            results.append(result)
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
        return any(results)
