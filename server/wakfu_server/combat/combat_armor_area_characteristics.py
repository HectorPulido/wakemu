"""Read actual partial Qq PCs for eWx arithmetic, without creating a fighter."""


def armor_area_characteristics(fight, identity):
    from .combat_state_managers import registered_area_pv, retained_area_pv_row
    from .combat_effect_area import native_effect_areas
    from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS

    pv = registered_area_pv(fight, identity)
    if pv is None:
        raise ValueError("Missing actual native armor target PV")
    row = retained_area_pv_row(fight, identity)
    definition = native_effect_areas()[str(row["reference"])]
    contract = row.get("native_area_contract")
    if contract == "faW":
        from .combat_fake_fighter import verified_fake_fighter
        from .combat_fake_fighter_resources import fake_fighter_characteristics

        constructor = verified_fake_fighter(row, definition)
        population = (
            fake_fighter_characteristics(row, definition)
            if constructor["characteristic_ids"]
            else {}
        )
        stats = {stat: values["current"] for stat, values in population.items()}
    elif contract == "fbd":
        from .combat_wall_area import wall_damage_snapshot

        stats = wall_damage_snapshot(row, definition)["stats"]
    elif contract == "fbc":
        from .combat_trap_area import verified_trap_characteristics

        stats = verified_trap_characteristics(row, definition)
    elif contract in SUPPORTED_AREA_CONTRACTS:
        # The other supported faV subtypes inherit a(PC)=false/b(PC)=null.
        if pv.native_characteristics is not None:
            raise ValueError("Changed native plain-area characteristic constructor")
        stats = {}
    else:
        raise ValueError("Unsupported native armor area characteristic authority")
    if not isinstance(stats, dict) or any(
        type(k) is not int or type(v) is not int for k, v in stats.items()
    ):
        raise ValueError("Missing actual native area characteristic values")
    if 97 in stats:
        # A present PA requires a separately qualified writer, not a fake Actor.
        raise ValueError("Native area armor PA writer is unavailable")
    return pv, stats
