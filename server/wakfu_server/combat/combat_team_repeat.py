"""eXM1041 count from actual fdt.saq current-team membership, not live HP."""
from .combat_repeated_group import RepeatSpecification


def team_repeat_specification(count):
    if type(count) is not int or not 0 <= count <= 12:
        raise ValueError("Missing actual native eXM repetition count")
    return RepeatSpecification(count, False)  # eXM.H always false.


def native_team_repeat_count(fight, caster_id):
    if caster_id is None:
        return 0  # Native G null caster branch.
    from .combat_state_managers import registered_area_pv, retained_area_pv_row
    from .combat_controller_registry import current_native_team
    from .combat_global_pv_collections import _collections
    from .combat_trove_long_map import NativeTroveLongMap

    if caster_id in fight.actors:
        team = current_native_team(fight, caster_id)
    else:
        area = registered_area_pv(fight, caster_id)
        if area is None:
            raise ValueError("Missing actual native eXM caster team authority")
        row = retained_area_pv_row(fight, caster_id)
        team = area.native_fight_affiliation
        # faV overrides Qq.bcM: j(PV) captures eGj.bcM into ebh, and
        # bcM returns that field. Do not re-read the owner's current team.
        if (
            row.get("native_fight_affiliation_source") != "faV.j(PV).bcM"
            or type(team) is not int
            or not -128 <= team < 128
        ):
            raise ValueError("Missing actual native faV captured team authority")
    state = _collections(fight)
    # fcb.bL -> fdt.a(fdZ): filter current bcM only. IN/OFF/OUT status,
    # HP, summon ownership and timeline membership are not part of this query.
    count = sum(
        current_native_team(fight, identity) == team
        for identity in NativeTroveLongMap(state["fighters"]).order()
    )
    return min(12, max(0, count - 1))
