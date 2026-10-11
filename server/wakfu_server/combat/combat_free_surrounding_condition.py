"""Native eMp cardinal-cell criterion, distinct from movement occupancy."""
from .combat_free_cell_condition import int32


def native_free_surrounding_cell(origin, *, terrain_free, first_obstacle):
    if origin is None:
        return False
    x, y = origin[:2]
    for px, py in (
        (int32(x + 1), y),
        (int32(x - 1), y),
        (x, int32(y + 1)),
        (x, int32(y - 1)),
    ):
        # eMp calls QI.V before Q/QI.R and ignores QI.U-only occupants.
        if not first_obstacle(px, py) and terrain_free(px, py):
            return True
    return False
