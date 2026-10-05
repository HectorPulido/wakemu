"""Mirror accredited casting1040 Lua facing on the private server preview.

Unsupported script contracts remain metadata pending; they do not invent a
rotation or reject otherwise valid spells. Cardinal/diagonal sectors follow aBz.
"""
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
    return json.loads(path.read_text())["spells"]


def mirror_cast_facing(caster, plan, *, contracts=None):
    record = (native_cast_facing() if contracts is None else contracts).get(
        str(plan["spell_id"])
    )
    if record is None or record.get("status") != "verified":
        return False
    if not record["turnCasterTowardTargetCell"]:
        return False
    target = plan["target"]
    # aiL computes Java signed-int deltas before aBA.bXz.
    delta = tuple(
        ((int(target[i]) - caster.position[i] + (1 << 31)) % (1 << 32)) - (1 << 31)
        for i in range(2)
    )
    direction = cast_direction(*delta, diagonals=record["useDiags"])
    if direction is None:
        return False  # aiL ignores the native NONE result.
    caster.direction = direction
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
