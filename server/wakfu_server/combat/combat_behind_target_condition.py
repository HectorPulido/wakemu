"""eNA: subtract actual bcy direction, then default eOV free-cell checks."""
from .combat_free_cell_condition import int32

# Installed aAS.dyI/dyJ/dyK; additional sentinels are qualified separately.
PLANAR_DIRECTIONS = (
    (1, -1),
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (-1, -1),
    (0, -1),
)


def native_behind_target_point(position, direction):
    if (
        not isinstance(position, (tuple, list))
        or len(position) != 3
        or any(type(value) is not int for value in position)
        or any(not -(1 << 31) <= value < (1 << 31) for value in position[:2])
        or not -32768 <= position[2] <= 32767
    ):
        raise ValueError("Missing actual eNA target coordinate")
    if type(direction) is not int or direction not in range(8):
        raise ValueError("Missing actual eNA planar bcy direction")
    dx, dy = PLANAR_DIRECTIONS[direction]
    # aBn.M subtracts its operands; unlike forced displacement this uses no pGJ.
    return (int32(position[0] - dx), int32(position[1] - dy), position[2])


def native_behind_target_free(fight, caster, target, authority):
    if target is None:
        return False  # eNA's unresolved eII.b target returns -1.
    if caster is None:
        return False  # Default eOV requires original source eGj.
    caster_kind = authority(fight, caster).targeting.get("is_eGj")
    if caster_kind is False:
        return False  # eOV returns -1 for a proven non-eGj source.
    if caster_kind is not True:
        raise ValueError("Missing actual eNA source eGj authority")
    if authority(fight, target).targeting.get("is_eGj") is not True:
        raise ValueError("Missing actual eNA target eHg authority")
    from .combat_qi_fight import current_registry
    from .combat_effect_area_targets import area_targets

    registry = current_registry(fight)
    x, y, _ = native_behind_target_point(target.position, target.direction)
    if not registry.snapshot().R(x, y):
        return False
    # eOV compares aBn.Y: actual Qq centers in XY, independent of altitude.
    for area in area_targets(fight):
        if tuple(area.position[:2]) == (x, y) and area.native_movement_blocking:
            return False
    return not registry.ordered_U(x, y)  # Actual first QI.V, including footprints.
