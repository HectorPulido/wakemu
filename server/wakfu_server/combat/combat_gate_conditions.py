"""Pure eMT gate presence over a complete Qs snapshot and actual QI.U facts."""


def _int32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def _gate_distance(cell, center):
    # ala.c(Qq,aBn), Qq.bcL ==0; Java int subtraction/abs/addition.
    distances = []
    for coordinate, other in zip(cell[:2], center[:2]):
        delta = _int32(coordinate - other)
        absolute = delta if delta == -(1 << 31) else abs(delta)
        distances.append(max(0, absolute))
    return _int32(sum(distances))


def has_valid_gate_for_tp(
    areas,
    *,
    caster_id,
    caster_affiliation,
    center,
    minimum,
    maximum,
    cell_affiliations=None,
):
    """eMT core after known fight/caster/center prerequisites.

    `areas` is the complete active Qs population, not a spatial subset. Each
    gate carries its actual captured faV.bcM value. The occupancy callback
    supplies complete QI.U signed-byte sets; empty means proven free. No
    ordering, destination choice, direct owner or current owner team is used.
    """
    if (
        not isinstance(areas, (tuple, list))
        or type(caster_id) is not int
        or type(caster_affiliation) is not int
        or not -128 <= caster_affiliation <= 127
        or any(
            type(v) is not int or not -(1 << 63) <= v < (1 << 63)
            for v in (minimum, maximum)
        )
        or not isinstance(center, (tuple, list))
        or len(center) != 3
        or any(
            type(v) is not int or not -(1 << 31) <= v < (1 << 31) for v in center[:2]
        )
    ):
        raise ValueError("Missing native gate predicate context")
    found = False
    for row in areas:
        if not isinstance(row, dict) or type(row.get("native_type_id")) is not int:
            raise ValueError("Missing complete native Qs type population")
        if row.get("uid") == caster_id or row["native_type_id"] != 19:
            continue
        affiliation = row.get("native_fight_affiliation")
        if type(affiliation) is not int or not -128 <= affiliation <= 127:
            raise ValueError("Missing captured native gate affiliation")
        if affiliation != caster_affiliation:
            continue
        cell = row.get("cell")
        if (
            not isinstance(cell, (tuple, list))
            or len(cell) != 3
            or any(
                type(v) is not int or not -(1 << 31) <= v < (1 << 31) for v in cell[:2]
            )
            or not callable(cell_affiliations)
        ):
            raise ValueError("Missing native gate cell/occupancy authority")
        occupants = cell_affiliations(cell[0], cell[1])
        if not isinstance(occupants, frozenset) or any(
            type(v) is not int or not -128 <= v <= 127 for v in occupants
        ):
            raise ValueError("Missing complete native QI.U cell affiliations")
        if occupants:
            continue
        distance = _gate_distance(cell, center)
        if maximum < 0 or minimum <= distance <= maximum:
            found = True
        # Native eMT scans/counts every candidate, including after a match.
    return found


def native_gate_count(areas, *, actor_id, affiliation, mode):
    """ePn: Qs type19 population, selected eGj and captured owner/team."""
    if mode.lower() not in ("forowner", "forteam") or actor_id is None:
        return 0
    total = 0
    for row in areas:
        if type(row.get("native_type_id")) is not int:
            raise ValueError("Missing native Qs gate type")
        if row["native_type_id"] != 19:
            continue
        if mode.lower() == "forowner":
            if "owner_id" not in row:
                raise ValueError("Missing native gate PV owner presence")
            total += row["owner_id"] == actor_id
        else:
            if (
                type(affiliation) is not int
                or type(row.get("native_fight_affiliation")) is not int
            ):
                raise ValueError("Missing captured native gate affiliation")
            total += row["native_fight_affiliation"] == affiliation
    return total
