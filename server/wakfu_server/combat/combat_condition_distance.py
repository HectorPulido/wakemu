"""Native GetDistanceBetweenCasterAndTarget geometry (eQb51/eQd/eJQ).

eJQ.d calls ala.c(alb,alb) or ala.c(alb,aBn), otherwise returns -1.
ala.c subtracts summed native bcL radii independently from each axis,
clamps each axis to zero, then adds. Height is ignored. This differs from
subtracting a radius from the total Manhattan distance.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DistanceActor:
    x: int
    y: int
    # Exact alb.bcL value, NOT a guessed graphical size or occupied cells.
    radius: int

    def __post_init__(self):
        if type(self.radius) is not int or not -128 <= self.radius <= 127:
            raise ValueError("Native radius must fit signed byte bcL")


def native_caster_target_distance(
    caster: DistanceActor | None,
    target: DistanceActor | tuple[int, int, int] | None,
) -> int:
    """Evaluate proven actor/actor, actor/cell and absent-target branches.

    None describes an actually absent native argument. Missing knowledge
    about an existing actor must not be encoded as None or radius zero.
    Cell tuples contain x,y,height; height has no role in ala.c.
    """
    if caster is None or target is None:
        return -1
    if isinstance(target, DistanceActor):
        x, y = target.x, target.y
        radius = caster.radius + target.radius
    elif isinstance(target, tuple) and len(target) == 3:
        x, y, _ = target
        radius = caster.radius
    else:
        raise ValueError("Target must be an authoritative native actor or cell")
    return max(0, abs(caster.x - x) - radius) + max(0, abs(caster.y - y) - radius)
