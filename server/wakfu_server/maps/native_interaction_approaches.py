"""Original bEG.dST/QV and VF.v/VA.a interaction approach selection."""
from wakfu_server.combat_geometry import coordinate, prepare_geometry
from wakfu_server.combat_sn_path import NativePhysicalSurface, NativeSnColumns


_DIRECTIONS = ((1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1))
# QV declaration order is observable: dST walks selected neighbors in reverse.
_RELATIVE = ((1, 0), (2, 4), (4, 6), (8, 2), (16, 1), (32, 7), (64, 3), (128, 5))


def _short(value):
    return ((value + 32768) % 65536) - 32768


def native_approach_height(surfaces, object_z):
    """VA.a: highest admitted native floor below objectZ+4, mover height6.

    Preserve ordered physical surfaces, signed thickness and the original
    single-surface branch. A missing floor returns None, never a guessed Z.
    """
    if type(object_z) is not int or not -32768 <= object_z <= 32767:
        raise ValueError("Invalid native interaction object altitude")
    if not isinstance(surfaces, (tuple, list)) or any(
        not isinstance(row, NativePhysicalSurface) for row in surfaces
    ):
        raise ValueError("Missing ordered native interaction physical surfaces")
    limit = _short(object_z + 4)
    if len(surfaces) == 1:
        row = surfaces[0]
        return None if row.through or row.bld == -1 or row.z > limit else row.z
    ceiling = 32767
    for row in reversed(surfaces):
        if row.through:
            continue
        if row.bld == -1 or row.z > limit or 6 > ceiling - row.z:
            ceiling = _short(row.z - row.thickness)
            continue
        return row.z
    return None


def native_interaction_approaches(
    geometry,
    object_position,
    *,
    direction,
    approach_mask,
    physical_columns,
    center_allowed=None
):
    """Generate actual QV approach cells from matching original map authority.

    Callers retain the object's decoded mask/orientation and original ordered
    Vy provider. Geometry filters disabled/unavailable floors; it never supplies
    replacement heights or bridges. No server catalog is loaded by this helper.
    """
    native = prepare_geometry(geometry)
    position = coordinate(object_position)
    if type(direction) is not int or not 0 <= direction <= 7:
        raise ValueError("Missing native interaction orientation")
    if type(approach_mask) is not int or not 0 <= approach_mask <= 511:
        raise ValueError("Invalid original QV interaction mask")
    if (
        not isinstance(physical_columns, NativeSnColumns)
        or physical_columns.map_id != native.map_id
    ):
        raise ValueError("Missing matching original interaction physical columns")
    result = []
    if approach_mask & 256:
        if type(center_allowed) is not bool:
            raise ValueError("Missing native interaction center occupation authority")
        if center_allowed and position in native.cells:
            result.append(position)
    for mask, relative in reversed(_RELATIVE):
        if not approach_mask & mask:
            continue
        dx, dy = _DIRECTIONS[(direction + relative) % 8]
        x, y = position[0] + dx, position[1] + dy
        surfaces = physical_columns.column(x, y)
        if surfaces is None:
            raise ValueError("Missing original interaction topology chunk")
        z = native_approach_height(surfaces, position[2])
        if z is not None and (x, y, z) in native.cells:
            result.append((x, y, z))
    return tuple(result)
