"""Exact current PV identity sources for dynamic ordered group contexts."""


def resolve_group_level_pv(fight, identity):
    if identity is None:
        return None
    from .combat_native_actor_lookup import native_actor
    from .combat_state_managers import registered_area_pv

    actor = native_actor(fight, identity)
    if actor is not None:
        return actor
    area = registered_area_pv(fight, identity)
    if area is None:
        raise ValueError(f"Missing native dynamic-group level-source PV: {identity}")
    return area


def scoped_group_actors(fight):
    """Qe holds the actual constructor PV before ordinary roster registration."""
    from .combat_summon_initialization import detached_actors

    actors = dict(fight.actors)
    for actor in detached_actors(fight):
        if actor.id in actors and actors[actor.id] is not actor:
            raise ValueError("Native group construction PV identity collision")
        actors[actor.id] = actor
    return actors


def group_pa(fight, identity, characteristic):
    """Return an actual PA (current,max), or source-proven PV.b(PC) null."""
    pv = resolve_group_level_pv(fight, identity)
    if pv is None:
        raise ValueError("Null PV has no PA lookup")
    if getattr(pv, "native_is_area", False) is True:
        from .combat_state_managers import retained_area_pv_row

        row = retained_area_pv_row(fight, identity)
        contract = row.get("native_area_contract")
        # These concrete classes inherit faV.b(PC), literally returning null.
        if contract in ("faY", "faZ", "faN", "faX", "faU", "fbb", "faP"):
            return None
        if contract == "fbc":
            from .combat_effect_area import native_effect_areas
            from .combat_trap_area import trap_pa_pair

            return trap_pa_pair(
                row, native_effect_areas()[str(row["reference"])], characteristic
            )
        if contract == "fbd":
            from .combat_effect_area import native_effect_areas
            from .combat_wall_area import wall_damage_snapshot

            snapshot = wall_damage_snapshot(
                row, native_effect_areas()[str(row["reference"])]
            )
            if characteristic not in snapshot["stats"]:
                return None
            if characteristic not in snapshot["maxima"]:
                raise ValueError("Missing native wall PA maximum authority")
            return snapshot["stats"][characteristic], snapshot["maxima"][characteristic]
        if contract == "faW":
            from .combat_effect_area import native_effect_areas
            from .combat_fake_fighter import verified_fake_fighter

            constructor = verified_fake_fighter(
                row, native_effect_areas()[str(row["reference"])]
            )
            if constructor["characteristic_ids"] == ():
                return None
            from .combat_fake_fighter_resources import fake_fighter_characteristics

            values = fake_fighter_characteristics(
                row, native_effect_areas()[str(row["reference"])]
            )
            pa = values.get(characteristic)
            return None if pa is None else (pa["current"], pa["maximum"])
        raise ValueError("Missing native area PA presence authority")
    current, maximum = pv.effect_stats, pv.effect_maxima
    if (
        not isinstance(current, dict)
        or not isinstance(maximum, dict)
        or characteristic not in current
        or characteristic not in maximum
    ):
        raise ValueError("Missing complete native PA characteristic snapshot")
    pair = current[characteristic], maximum[characteristic]
    if any(
        type(value) is not int or not -(1 << 31) <= value < (1 << 31) for value in pair
    ):
        raise ValueError("Invalid native PA current/maximum snapshot")
    return pair
