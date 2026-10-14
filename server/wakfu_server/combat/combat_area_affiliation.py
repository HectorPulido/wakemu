"""Read faV's constructor-captured affiliation consistently across consumers."""


def area_affiliation(fight, row):
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
