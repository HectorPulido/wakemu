"""Native class999/eYm: ordered eYg group with eVt.SP level override.

Actor levels are explicit eGj.cmZ snapshots, not levels inferred from IDs or
spell levels. Relative probability remains the common ordered-group guard.
"""
from dataclasses import replace
import math
from .combat_effect_groups import decode_group_mode, execute_ordered_group
from .combat_parameters import parameter_value, _float32, _integer
from .combat_native_timing_context import native_definition_timing
from .combat_native_events import validate_group_registration_flags


def _native_float_parameter(raw, index, level):
    increment = _float32(_float32(raw[2 * index + 1]) * level)
    rounded = (
        _integer(math.floor(increment + 0.5))
        if math.isfinite(increment)
        else _integer(increment)
    )
    if abs(_float32(increment - rounded)) < 1e-5:
        increment = _float32(rounded)
    return _float32(_float32(raw[2 * index]) + increment)


def level_group_override(effect, level, actor_level, *, return_native_override=False):
    raw = effect["parameters"]
    count = len(raw) // 2
    if count not in (8, 10):
        raise ValueError("Unknown native class999 parameter variant")
    if type(actor_level) is not int or not -32768 <= actor_level <= 32767:
        raise ValueError("Missing authoritative eGj.cmZ actor level")
    ratio = parameter_value(raw, 7, level)
    product = ((actor_level * ratio + (1 << 31)) % (1 << 32)) - (1 << 31)
    scaled = (
        abs(product) // 100 * (-1 if product < 0 else 1)
    )  # Java idiv truncates toward zero.
    base, growth = (
        (0.0, 1.0)
        if count == 8
        else (
            _native_float_parameter(raw, 8, level),
            _native_float_parameter(raw, 9, level),
        )
    )
    value = _float32(base + _float32(growth * _float32(scaled)))
    override = _integer(math.floor(value)) if math.isfinite(value) else _integer(value)
    # eVt.Oh == -1 preserves the container's original level; all other values
    # are cast to signed short by eZR.fRR.
    if return_native_override:
        return override
    return level if override == -1 else ((override + 32768) % 65536) - 32768


class NativeLevelGroupHandler:
    def __init__(
        self, *, execute_child, actor_level, actor_position, group_cells, active=None
    ):
        self.execute_child = execute_child
        self.actor_level = actor_level
        self.actor_position = actor_position
        self.group_cells = group_cells
        self.active = active

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 999:
            raise ValueError("Wrong native level group family")
        if effect["native_effect_flags"]:
            validate_group_registration_flags(
                effect["native_effect_flags"], active=self.active
            )
        native_definition_timing(effect, invocation.level)
        raw = effect["parameters"]
        count = len(raw) // 2
        if count not in (8, 10):
            raise ValueError("Unknown native class999 parameter variant")
        parameters = values["parameters"]
        mode = decode_group_mode(parameters[:6], raw_target_parameter=raw[4])
        caster, target = invocation.caster_id, invocation.target_id
        if mode.actor_rebind == 1:
            caster = target
        elif mode.actor_rebind == 2:
            caster, target = target, caster
        actor = caster if parameters[6] == 1 else target
        if actor is None:
            raise ValueError("Class999 level source requires native actor")
        level = level_group_override(effect, invocation.level, self.actor_level(actor))
        if level < 0:
            raise ValueError(
                "Native signed negative child level requires broader dispatcher contract"
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


def runtime_group_level(effect, values, invocation, actors, *, active=None):
    # Event-level flags use the same audited contract as the parent group.
    # No implicit fight mode is supplied for stand-alone callers.
    if effect["native_effect_flags"]:
        validate_group_registration_flags(effect["native_effect_flags"], active=active)
    native_definition_timing(effect, invocation.level)
    parameters = values["parameters"]
    mode = decode_group_mode(
        parameters[:6], raw_target_parameter=effect["parameters"][4]
    )
    caster, target = invocation.caster_id, invocation.target_id
    if mode.actor_rebind == 1:
        caster = target
    elif mode.actor_rebind == 2:
        caster, target = target, caster
    actor = actors.get(caster if parameters[6] == 1 else target)
    if actor is None:
        raise ValueError("Missing authoritative native group level actor")
    level = level_group_override(effect, invocation.level, actor.effective_level)
    if level < 0:
        raise ValueError(
            "Native negative child level requires broader dispatcher contract"
        )
    return level
