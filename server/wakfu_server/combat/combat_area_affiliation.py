"""Read faV's constructor-captured affiliation consistently across consumers."""


def area_affiliation(fight, row):
    if row.get("native_fight_affiliation_source") == "faV.constructor.null_owner":
        from .combat_state_managers import retained_area_pv_row

        if (
            type(row.get("uid")) is not int
            or retained_area_pv_row(fight, row["uid"]) is not row
            or row.get("owner_id") is not None
            or type(row.get("native_fight_affiliation")) is not int
            or row["native_fight_affiliation"] != -1
        ):
            raise ValueError("Missing actual neutral faV affiliation constructor")
        if row.get("native_environment_source") is not None:
            from .combat_environment_glyphs import verify_environment_glyph

            verify_environment_glyph(fight, row)
        elif row.get("native_area_contract") == "faP":
            from .combat_battleground_border import verify_battleground_border

            verify_battleground_border(fight, row)
        else:
            raise ValueError("Missing declared neutral faV constructor authority")
        return -1
    if "native_fight_affiliation" in row or "native_fight_affiliation_source" in row:
        value = row.get("native_fight_affiliation")
        if (
            type(value) is not int
            or not -128 <= value <= 127
            or row.get("native_fight_affiliation_source") != "faV.j(PV).bcM"
        ):
            raise ValueError("Missing captured native area affiliation bcM")
        return value
    # Older bounded fixtures omit the captured field entirely. Preserve their
    # explicit owner authority; an invalid supplied capture must never use it.
    owner = getattr(fight, "actors", {}).get(row.get("owner_id"))
    if owner is None:
        raise ValueError("Missing native area owner affiliation")
    value = getattr(owner, "native_fight_affiliation", getattr(owner, "team", None))
    if type(value) is not int or not -128 <= value <= 127:
        raise ValueError("Missing native area owner affiliation bcM")
    return value
