"""eJS: target distance to the nearest actual same-team BEACON Qq."""


def nearest_ally_beacon_distance(fight, *, caster_affiliation, target_position):
    # eJS returns -1 before enumerating fbX when its target is not alb/aBn.
    if target_position is None:
        return -1
    if type(caster_affiliation) is not int or not -128 <= caster_affiliation <= 127:
        raise ValueError("Missing native beacon caster bcM")
    if (
        not isinstance(target_position, (tuple, list))
        or len(target_position) != 3
        or any(type(v) is not int for v in target_position)
    ):
        raise ValueError("Missing native beacon target alb/aBn position")
    if not isinstance(getattr(fight, "native_effect_areas", None), dict):
        raise ValueError("Missing complete native beacon Qs population")
    from .combat_effect_area_queries import _rows

    closest = 32767  # Native Short.MAX_VALUE, including known empty Qs.
    for row in _rows(fight):
        kind = row.get("native_type_id")
        if kind is None and row.get("native_hour_contract") is True:
            kind = 1  # Verified faZ constructor, never an unknown BEACON.
        if type(kind) is not int:
            raise ValueError("Missing native Qq.aeV type authority")
        if kind != 2:  # fbp.rNJ.aIc() == BEACON == 2.
            continue
        affiliation = row.get("native_fight_affiliation")
        if type(affiliation) is not int or not -128 <= affiliation <= 127:
            raise ValueError("Missing captured native beacon Qq.bcM authority")
        if affiliation != caster_affiliation:
            continue
        cell = row.get("cell")
        if (
            not isinstance(cell, (tuple, list))
            or len(cell) != 3
            or any(type(v) is not int for v in cell)
        ):
            raise ValueError("Missing native beacon alb position")
        # ala.c(alb,aBn) uses XY; altitude does not enter the distance.
        distance = abs(cell[0] - target_position[0]) + abs(cell[1] - target_position[1])
        closest = min(closest, distance)
    return closest


def require_beacon_combat_context(*, detached):
    """eJS rejects eZQ instead of treating the surrounding fight as fbX."""
    if type(detached) is not bool:
        raise ValueError("Missing native beacon evaluation context")
    if detached:
        from .combat_native_criterion_failure import NativeCriterionRuntimeFailure

        raise NativeCriterionRuntimeFailure(
            "Native nearest-beacon criterion has no constructor combat context"
        )
