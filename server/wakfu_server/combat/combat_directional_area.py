"""eYU813 post-creation faV orientation, separate from initial callbacks."""
from .combat_orientation_effect import VECTORS


def directional_area_orientation(source, cell):
    if (
        not isinstance(source, tuple)
        or not isinstance(cell, tuple)
        or len(source) != 3
        or len(cell) != 3
        or any(type(value) is not int for value in (*source, *cell))
    ):
        raise ValueError("Missing actual eYU source/target coordinates")
    dx = ((cell[0] - source[0] + (1 << 31)) % (1 << 32)) - (1 << 31)
    dy = ((cell[1] - source[1] + (1 << 31)) % (1 << 32)) - (1 << 31)
    return (
        7
        if abs(dx) > 1 or abs(dy) > 1
        else -1
        if (dx, dy) == (0, 0)
        else VECTORS.index((dx, dy))
    )
