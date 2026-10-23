"""Verified faV subtypes share Qq PV identity, guards and PL namespace."""

AREA_CONTRACTS = {
    "BATTLEGROUND_BORDER": "faP",
    "HOUR": "faZ",
    "GLYPH": "faY",
    "AURA": "faN",
    "GATE": "faX",
    "FAKE_FIGHTER": "faW",
    "ENUTROF_DEPOSIT": "faU",
    "WALL": "fbd",
    "TRAP": "fbc",
    "SIMPLE": "fbb",
    "ARTIFACT": "faM",
}
SUPPORTED_AREA_CONTRACTS = frozenset(AREA_CONTRACTS.values())


def deposit_grade(definition):
    """faU.fTu is Java float-to-int of Qr.bdh parameter0, not area level."""
    import math
    from .combat_parameters import _float32

    parameters = definition.get("raw_bdh")
    if (
        definition.get("type") != "ENUTROF_DEPOSIT"
        or definition.get("native_class") != "bcK"
        or definition.get("native_type_id") != 12
        or definition.get("native_container_type") != 3
        or not isinstance(parameters, (list, tuple))
        or not parameters
        or type(parameters[0]) not in (int, float)
    ):
        raise ValueError("Missing native faU deposit constructor authority")
    value = _float32(parameters[0])
    if math.isnan(value):
        return 0
    return (
        -(1 << 31)
        if value <= -(1 << 31)
        else (1 << 31) - 1
        if value >= (1 << 31) - 1
        else int(value)
    )


def verified_deposit_grade(row, definition):
    grade = deposit_grade(definition)
    if (
        row.get("native_area_contract") != "faU"
        or type(row.get("native_deposit_grade")) is not int
        or row["native_deposit_grade"] != grade
        or row.get("native_deposit_grade_source") != "faU.fTu.Qr_bdh0"
    ):
        raise ValueError("Missing registered native faU grade provenance")
    return grade
