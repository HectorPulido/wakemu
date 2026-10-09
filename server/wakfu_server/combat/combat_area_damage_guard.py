"""Exact eXt.C/c HP-or-armor guard on actual partial Qq characteristic sets."""


def area_damage_has_no_resources(fight, identity):
    row = getattr(fight, "native_effect_areas", {}).get(identity)
    if row is None:
        return False
    from .combat_effect_area import native_effect_areas
    from .combat_state_managers import registered_area_pv
    from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS

    registered_area_pv(fight, identity)
    contract = row.get("native_area_contract")
    definition = native_effect_areas()[str(row["reference"])]
    if contract == "fbd":
        return False  # Actual fbd has sgC, handled by the wall damage writer.
    if contract == "fbc":
        from .combat_trap_area import verified_trap_characteristics

        values = verified_trap_characteristics(row, definition)
        # Actual export has only damage/healing PCs; no HP1 or armor97.
        if 1 in values or 97 in values:
            raise ValueError("Unexpected native fbc damage resource population")
        return True
    if contract == "faW":
        from .combat_fake_fighter import verified_fake_fighter

        constructor = verified_fake_fighter(row, definition)
        if constructor["characteristic_ids"]:
            raise ValueError("Unproduced native faW damage resource authority")
        return True
    if contract in SUPPORTED_AREA_CONTRACTS:
        return True  # Plain faV.a(PC) is false; no invented HP/armor snapshot.
    raise ValueError("Unknown native partial PV characteristic authority")
