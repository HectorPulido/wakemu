"""eNz: add actual bcy direction, then fbX.ay's XY fighter lookup."""
from .combat_behind_target_condition import (
    PLANAR_DIRECTIONS,
    native_behind_target_point,
)
from .combat_free_cell_condition import int32


def native_caster_facing_point(position, direction):
    # Reuse the exact planar direction/coordinate validation, then aBn.e adds.
    native_behind_target_point(position, direction)
    dx, dy = PLANAR_DIRECTIONS[direction]
    return (int32(position[0] + dx), int32(position[1] + dy), position[2])


def native_caster_facing_fighter(fight, caster, authority):
    if caster is None or authority(fight, caster).targeting.get("is_eGj") is not True:
        raise ValueError("Missing actual eNz source eHg authority")
    from .combat_qi_fight import current_registry

    registry = current_registry(fight)
    x, y, _ = native_caster_facing_point(caster.position, caster.direction)
    for slot in registry.ordered_U(x, y):
        kind, identity = registry.slots[slot]["identity"]
        if kind == "effect_area":
            continue  # fcb.dC skips Qq and returns the first actual eGj.
        if kind != "actor":
            raise ValueError("Missing actual eNz registered QK type")
        actor = fight.actors.get(identity)
        if actor is None:
            raise ValueError("Missing actual eNz registered fighter")
        is_fighter = authority(fight, actor).targeting.get("is_eGj")
        if type(is_fighter) is not bool:
            raise ValueError("Missing actual eNz registered eGj authority")
        if is_fighter:
            return True
    return False
