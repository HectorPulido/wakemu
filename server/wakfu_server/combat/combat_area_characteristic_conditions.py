"""Condition PCs from the actual registered area's partial constructor universe."""


def area_characteristic_snapshot(fight, identity):
    from .combat_armor_area_characteristics import armor_area_characteristics
    from .combat_area_total_hp_conditions import area_total_hp_snapshot
    from .combat_characteristic_conditions import characteristic_ids
    from .combat_state_managers import retained_area_pv_row
    from .combat_effect_area import native_effect_areas

    _pv, stats = armor_area_characteristics(fight, identity)
    hp_current, hp_maxima, hp_absent = area_total_hp_snapshot(fight, identity)
    ids = characteristic_ids()
    # eJy.d checks eHg.a(PC) before reading its PA. A source-proven absent
    # non-HP PC is None, which the shared condition evaluator returns as-1.
    # HP retains its separate total-HP absence contract and existing readers.
    current = {name: stats.get(pc) for name, pc in ids.items() if name not in hp_absent}
    maxima = {
        name: None
        for name, pc in ids.items()
        if pc not in stats and name not in hp_absent
    }
    row = retained_area_pv_row(fight, identity)
    definition = native_effect_areas()[str(row["reference"])]
    if row["native_area_contract"] == "faW":
        from .combat_fake_fighter import verified_fake_fighter
        from .combat_fake_fighter_resources import fake_fighter_characteristics

        constructor = verified_fake_fighter(row, definition)
        population = (
            fake_fighter_characteristics(row, definition)
            if constructor["characteristic_ids"]
            else {}
        )
        maxima.update(
            {
                name: population[pc]["maximum"]
                for name, pc in ids.items()
                if pc in population
            }
        )
    elif row["native_area_contract"] == "fbc":
        from .combat_trap_area import trap_pa_pair

        maxima.update(
            {
                name: trap_pa_pair(row, definition, pc)[1]
                for name, pc in ids.items()
                if pc in stats
            }
        )
    # Wall non-HP maxima remain unknown until a native PA maximum is qualified.
    current.update(hp_current)
    maxima.update(hp_maxima)
    return current, maxima, hp_absent
