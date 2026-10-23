"""Native faW.aQc sgQ-only construction with an explicit owner PA snapshot."""
from .combat_fake_fighter import _float32, _int

SOURCE = "faW.aQc.sgQ_only.owner_snapshot.v1"
# faW.aQc adds these owner PCs in bytecode order through PA.nG.
COPY_FIELDS = ((1, 20), (2, 21), (4, 22), (8, 23), (16, 24))


def damage_only_mask(definition):
    raw = definition.get("raw_bdh")
    if not isinstance(raw, (list, tuple)) or len(raw) != 10:
        return None
    values = tuple(_float32(value) for value in raw)
    if values[1] != -1 or not 0 <= values[9] <= 31:
        return None
    if (
        definition.get("type") != "FAKE_FIGHTER"
        or definition.get("native_type_id") != 15
        or definition.get("native_class") != "bcQ"
    ):
        raise ValueError("Missing native faW sgQ-only prototype")
    return _int(values[9])


def _damage_only_mask_from_parameters(definition, values):
    """Pure branch selection from this call's already rounded parameters."""
    if len(values) != 10:
        return None
    if values[1] != -1 or not 0 <= values[9] <= 31:
        return None
    if (
        definition.get("type") != "FAKE_FIGHTER"
        or definition.get("native_type_id") != 15
        or definition.get("native_class") != "bcQ"
    ):
        raise ValueError("Missing native faW sgQ-only prototype")
    return _int(values[9])


def constructor(definition, owner_stats):
    return _constructor_from_mask(damage_only_mask(definition), owner_stats)


def _constructor_from_mask(mask, owner_stats):
    if mask is None or not isinstance(owner_stats, dict):
        raise ValueError("Missing native faW sgQ-only owner snapshot")
    current = 0
    captured = {}
    for flag, identity in COPY_FIELDS:
        if not mask & flag:
            continue
        value = owner_stats.get(identity, owner_stats.get(str(identity)))
        # PV.a(PC) controls presence; absent owner PCs contribute nothing.
        captured[str(identity)] = value
        if value is None:
            continue
        if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
            raise ValueError("Invalid native faW owner characteristic value")
        # PA.nG uses Java int addition before clamping each ordered delta.
        summed = ((current + value + (1 << 31)) % (1 << 32)) - (1 << 31)
        current = max(-5000, min(50000, summed))
    return dict(
        source=SOURCE,
        mask=mask,
        owner_stats=captured,
        characteristics={
            20: dict(
                current=current,
                minimum=-5000,
                maximum=50000,
                absolute_minimum=-5000,
                absolute_maximum=50000,
            )
        },
    )


def install(row, definition, owner_stats):
    receipt = constructor(definition, owner_stats)
    row["native_faw_damage_only_constructor"] = receipt
    row["native_faw_damage_current"] = receipt["characteristics"][20]["current"]
    row["native_faw_damage_source"] = "faW.PA.sgQ.aYS"
    return characteristics(row, definition)


def characteristics(row, definition):
    receipt = row.get("native_faw_damage_only_constructor")
    if not isinstance(receipt, dict):
        raise ValueError("Missing native faW sgQ-only constructor receipt")
    return _characteristics_from_mask(row, damage_only_mask(definition), receipt)


def _characteristics_from_mask(row, mask, receipt=None):
    """Reuse pure selection; validate the actual receipt/current on every call."""
    if receipt is None:
        receipt = row.get("native_faw_damage_only_constructor")
    if not isinstance(receipt, dict):
        raise ValueError("Missing native faW sgQ-only constructor receipt")
    expected = _constructor_from_mask(mask, receipt.get("owner_stats"))
    # JSON restoration changes integer dictionary keys to strings.
    stored = dict(
        receipt,
        characteristics={
            int(k): v for k, v in receipt.get("characteristics", {}).items()
        },
    )
    current = row.get("native_faw_damage_current")
    if (
        stored != expected
        or row.get("native_faw_damage_source") != "faW.PA.sgQ.aYS"
        or type(current) is not int
        or not -5000 <= current <= 50000
        or any(key.startswith("native_faw_hp_") for key in row)
    ):
        raise ValueError("Missing actual native faW sgQ-only PA authority")
    return {20: dict(expected["characteristics"][20], current=current)}
