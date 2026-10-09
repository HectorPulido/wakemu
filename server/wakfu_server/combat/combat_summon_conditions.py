"""eMI HasSummonWithBreed over complete native fUQ ownership facts.

Unlike NbSummons/dTB, eMI does not filter HP, offplay or summon flags. It checks
an exact short breed promoted to long, a distinct actor, and direct dpu owner.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SummonBreedRow:
    actor_id: int
    breed: int
    direct_owner_id: int
    position: tuple | None = None


def surrounding_own_summon(rows, *, caller_id, center, breed=-1, mode="VON_NEUMANN"):
    """eMP: direct dpu/fUQ population; includes center and ignores life flags."""
    if caller_id is None or center is None:
        return False
    if (
        not isinstance(center, (tuple, list))
        or len(center) != 3
        or any(
            type(value) is not int or not -(1 << 31) <= value < (1 << 31)
            for value in center[:2]
        )
    ):
        raise ValueError("Missing native neighborhood center")
    if not isinstance(mode, str) or mode.upper() not in ("MOORE", "VON_NEUMANN"):
        raise ValueError("Unknown native eMK neighborhood enum")
    if type(breed) is not int or not -(1 << 63) <= breed < 1 << 63 or rows is None:
        raise ValueError("Missing native neighborhood breed/population")
    int32 = lambda value: ((value + (1 << 31)) % (1 << 32)) - (1 << 31)
    xs = (int32(center[0] - 1), center[0], int32(center[0] + 1))
    ys = (int32(center[1] - 1), center[1], int32(center[1] + 1))
    for row in rows:
        if (
            not isinstance(row, SummonBreedRow)
            or type(row.actor_id) is not int
            or type(row.direct_owner_id) is not int
            or type(row.breed) is not int
            or not -32768 <= row.breed < 32768
        ):
            raise ValueError("Missing native dpu/aXA row")
        if row.actor_id == caller_id or row.direct_owner_id != caller_id:
            continue
        if breed != -1 and row.breed != breed:
            continue
        if (
            not isinstance(row.position, (tuple, list))
            or len(row.position) != 3
            or any(
                type(value) is not int or not -(1 << 31) <= value < (1 << 31)
                for value in row.position[:2]
            )
        ):
            raise ValueError("Missing native owned summon position")
        x, y = row.position[:2]
        if mode.upper() == "MOORE":
            if x in xs and y in ys:
                return True
        elif x == center[0] and y in ys or y == center[1] and x in xs:
            return True
    return False


def has_summon_with_breed(rows, *, caller_id, breed):
    if type(breed) is not int or not -(1 << 63) <= breed < 1 << 63:
        raise ValueError("Native summon breed requires evaluated long")
    if caller_id is None:
        return False  # eMI: non-amP caller -> -1.
    if type(caller_id) is not int or rows is None:
        raise ValueError("Missing complete native summon breed roster")
    for row in rows:
        if (
            not isinstance(row, SummonBreedRow)
            or type(row.actor_id) is not int
            or type(row.direct_owner_id) is not int
            or type(row.breed) is not int
            or not -32768 <= row.breed < 32768
        ):
            raise ValueError("Missing native dpu/aXA actor identity")
        if (
            row.actor_id != caller_id
            and row.breed == breed
            and row.direct_owner_id == caller_id
        ):
            return True
    return False
