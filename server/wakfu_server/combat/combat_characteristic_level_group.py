"""Native913/eYn ordered group levels from a selected PA characteristic.

Uses the same audited arithmetic as its1047/eYs subclass, without adding
virtual HP or interpreting missing snapshots as invented zero values.
"""
from dataclasses import replace
from .combat_hp_level_group import _value_group_override
from .combat_parameters import parameter_value
from .combat_effect_groups import decode_group_mode, execute_ordered_group
from .combat_native_timing_context import native_definition_timing
from .combat_actor_snapshot import native_actor_catalog


def characteristic_group_override(
    effect, level, *, current, maximum, return_native_override=False
):
    if effect["effect_class"] != 913:
        raise ValueError("Wrong native characteristic group family")
    if any(
        type(v) is not int or not -(1 << 31) <= v < (1 << 31)
        for v in (current, maximum)
    ):
        raise ValueError("Missing authoritative native characteristic current/maximum")
    return _value_group_override(
        effect,
        level,
        current=current,
        maximum=maximum,
        return_native_override=return_native_override,
    )


def runtime_group_level(
    effect, values, invocation, actors, *, return_native_override=False
):
    if effect["effect_class"] != 913:
        raise ValueError("Wrong native characteristic group family")
    native_definition_timing(effect, invocation.level)
    parameters = values["parameters"]
    raw = effect["parameters"]
    if len(parameters) not in (9, 10, 11, 12):
        raise ValueError("Unknown native913 parameter variant")
    # eYn.C casts parameter6 to signed byte before ffw.fK; exported PA keys
    # preserve that byte's unsigned encoding (e.g.132 and -124 name same PC).
    stat = parameter_value(raw, 6, invocation.level) & 255
    if str(stat) not in native_actor_catalog()["characteristics"]:
        return -1 if return_native_override else invocation.level
    mode = decode_group_mode(parameters[:6], raw_target_parameter=raw[4])
    caster, target = invocation.caster_id, invocation.target_id
    if mode.actor_rebind == 1:
        caster = target
    elif mode.actor_rebind == 2:
        caster, target = target, caster
    identity = caster if parameters[7] == 1 else target
    if identity is None:
        return -1 if return_native_override else invocation.level
    actor = actors.get(identity)
    if actor is None:
        raise ValueError("Missing native characteristic-group actor")
    if (
        not isinstance(actor.effect_stats, dict)
        or not isinstance(actor.effect_maxima, dict)
        or stat not in actor.effect_stats
        or stat not in actor.effect_maxima
    ):
        raise ValueError("Missing complete native PA characteristic snapshot")
    return characteristic_group_override(
        effect,
        invocation.level,
        current=actor.effect_stats[stat],
        maximum=actor.effect_maxima[stat],
        return_native_override=return_native_override,
    )


class NativeCharacteristicLevelGroupHandler:
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
