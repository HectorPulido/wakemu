"""Source-qualified eLB HP PCs for actual registered faV recipients.

Maps contain only present HP/VIRTUAL_HP PCs. Known absence is separate and
consumed by eLB/eJz, never an invented characteristic or general zero default.
"""


def area_total_hp_snapshot(fight, identity):
    from .combat_state_managers import registered_area_pv, retained_area_pv_row
    from .combat_effect_area import native_effect_areas
    from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS
    from .combat_characteristic_conditions import characteristic_ids

    pv = registered_area_pv(fight, identity)
    if pv is None:
        raise ValueError("Missing registered native total HP area PV")
    row = retained_area_pv_row(fight, identity)
    definition = native_effect_areas()[str(row["reference"])]
    contract = row.get("native_area_contract")
    ids = characteristic_ids()
    wanted = {name: ids[name] for name in ("HP", "VIRTUAL_HP")}
    current, maxima, absent = {}, {}, set()
    if contract == "faW":
        from .combat_fake_fighter import verified_fake_fighter
        from .combat_fake_fighter_resources import fake_fighter_characteristics

        constructor = verified_fake_fighter(row, definition)
        population = (
            fake_fighter_characteristics(row, definition)
            if constructor["characteristic_ids"]
            else {}
        )
        if set(population) != set(constructor["characteristic_ids"]):
            raise ValueError("Changed native faW total HP characteristic universe")
        for name, pc in wanted.items():
            if pc not in population:
                absent.add(name)
            else:
                current[name] = population[pc]["current"]
                maxima[name] = population[pc]["maximum"]
    elif contract == "fbd":
        from .combat_wall_area import verified_wall_constructor, wall_hp_state

        # fbd.aQc creates HP (sgC=1) plus rMK, which excludes virtual HP92.
        # Keep actual retired-QI authority: wall_damage_snapshot has no fight
        # argument, while synchronous Qs callbacks still own this same PV.
        if wanted != {"HP": 1, "VIRTUAL_HP": 92}:
            raise ValueError("Changed native fbd HP characteristic identities")
        constructor = verified_wall_constructor(row, definition, fight=fight)
        hp = wall_hp_state(row, constructor)
        current["HP"] = hp["current"]
        maxima["HP"] = hp["maximum"]
        absent.add("VIRTUAL_HP")
    elif contract == "fbc":
        from .combat_trap_area import verified_trap_characteristics, trap_pa_pair

        population = verified_trap_characteristics(row, definition)
        for name, pc in wanted.items():
            if pc not in population:
                absent.add(name)
            else:
                current[name], maxima[name] = trap_pa_pair(row, definition, pc)
    elif contract in SUPPORTED_AREA_CONTRACTS:
        # Supported remaining faV subtypes inherit a(PC)=false/b(PC)=null.
        if pv.native_characteristics is not None:
            raise ValueError("Changed native plain-area HP characteristic universe")
        absent.update(wanted)
    else:
        raise ValueError("Unsupported native total HP area characteristic authority")
    if any(type(value) is not int for value in (*current.values(), *maxima.values())):
        raise ValueError("Missing actual native area HP characteristic values")
    return current, maxima, frozenset(absent)
