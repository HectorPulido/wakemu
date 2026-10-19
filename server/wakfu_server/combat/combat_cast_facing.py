"""Face admitted casts toward their cell under the requested server policy.

Known literal native exceptions take precedence over the cardinal default.
Verified1040 presentation/finish contracts retain their native timing semantics.
All mutations and wire packets remain inside the private cast transaction.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
import math
import struct
from functools import lru_cache
from pathlib import Path
from .combat_displacement_geometry import cardinal_vector

DIRECTIONS = {(1, 0): 1, (0, 1): 3, (-1, 0): 5, (0, -1): 7}


@lru_cache(maxsize=1)
def native_cast_facing():
    path = Path(__file__).parents[2] / "protocol/native-cast-facing.json"
    spells = protocol_catalog.load(path)["spells"]
    from .combat_cast_facing_contracts import SCRIPT_CONTRACTS

    result = dict(spells)
    for reference, record in spells.items():
        supplement = SCRIPT_CONTRACTS.get(record.get("script_id"))
        if supplement is not None:
            combined = dict(record)
            for name, value in supplement.items():
                combined.setdefault(name, value)
            result[reference] = combined
    return result


def mirror_cast_facing(caster, plan, *, fight=None, contracts=None):
    # Weapons have no casting-script contract; use the same requested default.
    record = (
        {}
        if "spell_id" not in plan
        else (native_cast_facing() if contracts is None else contracts).get(
            str(plan["spell_id"]), {}
        )
    )
    if record.get("turnCasterTowardTargetCell") is False:
        return False
    target = plan["target"]
    # aiL computes Java signed-int deltas before aBA.bXz.
    delta = _java_xy_delta(caster.position, target)
    direction = cast_direction(*delta, diagonals=record.get("useDiags") is True)
    if direction is None:
        return False  # aiL ignores the native NONE result.
    if fight is None or fight.actors.get(caster.id) is not caster:
        raise ValueError("Casting facing requires the actual registered preview actor")
    from .combat_carrying import set_registered_direction

    set_registered_direction(fight, caster, direction)
    return True


def begin_cast_facing(caster, plan, *, fight, action_id, contracts=None):
    """Prepare facing before cast animation/effects, with its own FIFO block."""
    before = caster.direction
    mirrored = mirror_cast_facing(caster, plan, fight=fight, contracts=contracts)
    if not mirrored or caster.direction == before:
        return ()
    from .combat_orientation import facing_response

    return (
        facing_response(fight.id, action_id, caster.id, caster.direction),
        (13420, struct.pack(">i", fight.id)),
    )


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
