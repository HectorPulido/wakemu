"""Mirror accredited casting1040 Lua facing on the private server preview.

Unsupported script contracts remain metadata pending; they do not invent a
rotation or reject otherwise valid spells. Cardinal/diagonal sectors follow aBz.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
import math
import struct
from functools import lru_cache
from pathlib import Path
from .combat_displacement import cardinal_vector

DIRECTIONS = {(1, 0): 1, (0, 1): 3, (-1, 0): 5, (0, -1): 7}


@lru_cache(maxsize=1)
def native_cast_facing():
    path = Path(__file__).parents[2] / "protocol/native-cast-facing.json"
    return protocol_catalog.load(path)["spells"]


def mirror_cast_facing(caster, plan, *, fight=None, contracts=None):
    record = (native_cast_facing() if contracts is None else contracts).get(
        str(plan["spell_id"])
    )
    if record is None or record.get("status") != "verified":
        return False
    if not record["turnCasterTowardTargetCell"]:
        return False
    target = plan["target"]
    # aiL computes Java signed-int deltas before aBA.bXz.
    delta = _java_xy_delta(caster.position, target)
    direction = cast_direction(*delta, diagonals=record["useDiags"])
    if direction is None:
        return False  # aiL ignores the native NONE result.
    if fight is None or fight.actors.get(caster.id) is not caster:
        raise ValueError("Casting facing requires the actual registered preview actor")
    from .combat_carrying import set_registered_direction

    set_registered_direction(fight, caster, direction)
    return True


def _java_xy_delta(position, target):
    """aiL subtracts signed Java ints before choosing a facing sector."""
    return tuple(
        ((int(target[i]) - int(position[i]) + (1 << 31)) % (1 << 32)) - (1 << 31)
        for i in range(2)
    )


def finish_mirrored_cast_facing(
    caster,
    plan,
    *,
    fight,
    contracts=None,
):
    """Persist 1040's delayed cardinal look-at before actor refresh serialization.

    The common Lua template first turns diagonally for cast presentation, then
    schedules an unconditional cardinal look-at after the caster animation.
    """
    record = (native_cast_facing() if contracts is None else contracts).get(
        str(plan["spell_id"])
    )
    if (
        record is None
        or record.get("status") != "verified"
        or record.get("template") != 1040
        or not record.get("useDiags", False)
        or record.get("casterAnimOnTarget", False)
    ):
        return False
    if fight is None or fight.actors.get(caster.id) is not caster:
        raise ValueError("Casting finish facing requires the registered preview actor")
    dx, dy = _java_xy_delta(caster.position, plan["target"])
    direction = cast_direction(dx, dy, diagonals=False)
    if direction is None:
        return False  # aiL ignores the native NONE result for same-cell look-at.
    from .combat_carrying import set_registered_direction

    set_registered_direction(fight, caster, direction)
    return True


def cast_direction(dx, dy, *, diagonals):
    """aiL NONE guard then aBA.bXz or aBA.bo float32 native sectors."""
    if dx == 0 and dy == 0:
        return None
    if not diagonals:
        return DIRECTIONS[cardinal_vector(dx, dy)]

    def f32(value):
        return struct.unpack(">f", struct.pack(">f", value))[0]

    angle = -f32(math.atan2(f32(dy), f32(dx)))
    # Exact Java float constants from aBz.bo; lower inclusive, upper exclusive.
    bounds = (0.3926991, 1.1780972, 1.9634955, 2.7488937)
    a, b, c, d = map(f32, bounds)
    for lower, upper, direction in (
        (c, d, 6),
        (b, c, 7),
        (a, b, 0),
        (-a, a, 1),
        (-b, -a, 2),
        (-c, -b, 3),
        (-d, -c, 4),
    ):
        if lower <= angle < upper:
            return direction
    return 5
