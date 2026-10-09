"""eNR rotated free-cell predicate; distinct from casting QI.g."""


def int32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def native_cell_direction(origin, other):
    dx, dy = (int32(other[i] - origin[i]) for i in range(2))
    if not dx and not dy:
        return None
    absolute = lambda value: value if value == -(1 << 31) else abs(value)
    if not dy or dx and absolute(dx) > absolute(dy):
        return (1 if dx > 0 else -1, 0)
    return (0, 1 if dy > 0 else -1)


def native_free_cell(
    origin, other, forward, sideways, *, terrain_free, area_blockers, first_obstacle
):
    if origin is None or other is None:
        return False
    direction = native_cell_direction(origin, other)
    if direction is None:
        return False
    dx, dy = direction
    forward, sideways = int32(forward), int32(sideways)
    point = (
        int32(origin[0] + int32(dx * forward - dy * sideways)),
        int32(origin[1] + int32(dy * forward + dx * sideways)),
    )
    if not terrain_free(*point):
        return False
    for center, blocks in area_blockers:
        if type(blocks) is not bool:
            raise ValueError("Missing native Qq.bcP authority")
        if tuple(center[:2]) == point and blocks:
            return False
    return not first_obstacle(*point)
