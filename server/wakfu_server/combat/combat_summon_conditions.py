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
