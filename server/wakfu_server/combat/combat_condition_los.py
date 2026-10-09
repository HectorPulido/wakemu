"""eMr HasLineOfSight: ordered eII.aR endpoints with actual fcr/QI rays."""


def native_condition_los(
    fight,
    authority,
    caster_id,
    target_id,
    cell,
    *,
    actor_property_authority=None,
    target_is_cell=False
):
    from .combat_conditions import UnknownCondition
    from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS
    from .combat_casting_los import native_casting_los
    from .combat_qi_fight import current_registry

    source = fight.actors.get(caster_id)
    if source is None:
        return False
    authority(fight, source)
    if actor_property_authority is None:
        raise UnknownCondition("Missing actual condition LOS fight-property authority")
    target = fight.actors.get(target_id)
    if target_is_cell or target_id is None:
        if cell is None:
            return False
        point = tuple(cell)
        # The aBn argument remains a single endpoint; its fighter alias supplies
        # height only. Native dC independently resolves the first actual eGj.
        target = None
        registry = current_registry(fight)
        for slot in registry.ordered_U(*point[:2]):
            row = registry.slots[slot]
            if row is None or row["identity"][0] != "actor":
                continue
            candidate = fight.actors[row["identity"][1]]
            native_type = authority(fight, candidate).targeting.get("is_eGj")
            if type(native_type) is not bool:
                raise UnknownCondition("Missing actual condition LOS target type")
            if native_type:
                target = candidate
                break
        endpoints = (point,)
    elif target is None:
        row = getattr(fight, "native_effect_areas", {}).get(target_id)
        if row is None:
            raise UnknownCondition("Missing actual condition LOS target identity")
        if row.get("native_area_contract") not in SUPPORTED_AREA_CONTRACTS:
            return False  # Plain Qq is not eHg; actual faV implements eHg.
        from .combat_state_managers import registered_area_pv

        target = registered_area_pv(fight, target_id)
        if (
            target is None
            or type(getattr(target, "native_los_height", None)) is not int
        ):
            raise UnknownCondition("Missing actual condition LOS area height")
        endpoints = (tuple(target.position),)  # Qq.bcL literal zero.
    else:
        authority(fight, target)
        radius = target.physical_radius
        point = tuple(target.position)
        if type(radius) is not int or not 0 <= radius <= 127:
            raise UnknownCondition(
                "Missing supported native condition LOS target radius"
            )
        if (
            len(point) != 3
            or any(type(v) is not int for v in point)
            or any(
                not -(1 << 31) <= v - radius <= v + radius < (1 << 31) - 1
                for v in point[:2]
            )
        ):
            raise UnknownCondition("Native condition LOS footprint loop overflows")
        endpoints = (
            (x, y, point[2])
            for x in range(point[0] - radius, point[0] + radius + 1)
            for y in range(point[1] - radius, point[1] + radius + 1)
        )
    for endpoint in endpoints:
        try:
            if native_casting_los(
                fight, actor_property_authority, caster_id, endpoint, target
            ):
                return True
        finally:
            fight.native_qi_visibility_ignored_slots = []  # fcr finally: QI.bdM.
    return False
