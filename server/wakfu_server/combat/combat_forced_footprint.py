"""Original faz.a(IIS,fay): ordered square footprint, then center transition."""
from dataclasses import dataclass
from functools import lru_cache
from .combat_casting_range import int32
from .combat_sn_path import native_sm_transitions


@lru_cache(maxsize=4)
def forced_physical_columns(map_id):
    from .combat_sn_path import NativeSnColumns

    return NativeSnColumns.from_published(map_id)


@dataclass(frozen=True)
class ForcedFootprintStep:
    destination: tuple[int, int, int] | None
    collision: bool = False
    collider_id: int | None = None
    destination_index: int | None = None


def forced_footprint_step(
    source,
    xy,
    *,
    radius,
    height,
    physical_column,
    terrain_valid,
    obstruction,
    source_index=None,
):
    """Use actual VB.a columns; each offset compares the SAME source center.

    Sm.a's seven-argument overload never reads its stored radius (boC).
    faz performs that radius loop itself, X outermost, Y innermost, then
    checks the center again and takes its FIRST Sm.boE surface.
    """
    if type(radius) is not int or not 0 <= radius <= 127:
        raise ValueError("Missing native forced footprint radius")
    if type(height) is not int or not -128 <= height <= 127:
        raise ValueError("Missing actual native forced physical height")
    start = physical_column(*source[:2])
    if not start:
        raise ValueError("Missing actual forced source physical column")
    index = source_index
    if index is None:
        index = next(
            (i for i in range(len(start) - 1, -1, -1) if start[i].z == source[2]), None
        )
    if index is None:
        raise ValueError("Missing exact native VA source altitude")
    if (
        type(index) is not int
        or not 0 <= index < len(start)
        or start[index].z != source[2]
    ):
        raise ValueError("Changed native faz source surface index")
    points = [
        (int32(xy[0] + dx), int32(xy[1] + dy))
        for dx in range(-radius, radius + 1)
        for dy in range(-radius, radius + 1)
    ]
    points.append(tuple(xy))
    destination = None
    for x, y in points:
        end = physical_column(x, y)
        if end is None:
            # faz.fW cannot locate a VB: faw.aIm aborts without collision.
            return ForcedFootprintStep(None)
        if not terrain_valid(x, y):
            return ForcedFootprintStep(None, True)
        choices = native_sm_transitions(index, start, end, height=height, jump=4)
        if not choices:
            return ForcedFootprintStep(None, True)
        blocked, collider = obstruction((x, y, source[2]))
        if blocked:
            return ForcedFootprintStep(None, True, collider)
        destination = (x, y, end[choices[0]].z)
    return ForcedFootprintStep(destination, destination_index=choices[0])
