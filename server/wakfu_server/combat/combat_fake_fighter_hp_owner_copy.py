"""Native faW.aQc combined sgC/sgQ branch with frozen original owner PCs.

The existing HP producer owns float32 level arithmetic. The existing owner-copy
producer owns ordered PA.nG additions/clamps. This composes those independent
native branches without inventing either characteristic when it is absent.
"""
from .combat_fake_fighter import _float32, _int

SOURCE = "faW.aQc.sgC_sgQ.owner_snapshot.v1"


def mask_from_parameters(definition, parameters):
    if (
        len(parameters) != 10
        or parameters[1] == -1
        or parameters[9] == 0
        or not 0 <= parameters[9] <= 31
    ):
        return None
    if (
        definition.get("type") != "FAKE_FIGHTER"
        or definition.get("native_type_id") != 15
        or definition.get("native_class") != "bcQ"
    ):
        raise ValueError("Missing native faW combined HP/owner-copy prototype")
    return _int(parameters[9])


def mask(definition):
    raw = definition.get("raw_bdh")
    if not isinstance(raw, (list, tuple)) or len(raw) != 10:
        return None
    copy = _float32(raw[9])
    if copy == 0 or not 0 <= copy <= 31:
        return None
    hp = _float32(raw[1])
    return mask_from_parameters(definition, (0, hp, 0, 0, 0, 0, 0, 0, 0, copy))


def constructor(definition, level, owner_stats):
    from .combat_fake_fighter_resources import _hp_resources_from_parameters
    from .combat_fake_fighter_owner_copy import _constructor_from_mask

    selected = mask(definition)
    if selected is None:
        raise ValueError("Missing native faW combined HP/owner-copy branch")
    raw = definition["raw_bdh"]
    hp = _hp_resources_from_parameters(dict(definition, raw_bdh=[*raw[:9], -1]), level)
    damage = _constructor_from_mask(selected, owner_stats)
    return dict(
        source=SOURCE,
        level=level,
        mask=selected,
        owner_stats=damage["owner_stats"],
        characteristics={
            1: hp["characteristics"][1],
            20: damage["characteristics"][20],
        },
    )


def owned_resources(row, definition):
    receipt = row.get("native_faw_hp_owner_copy_constructor")
    if type(receipt) is not dict:
        raise ValueError("Missing native faW combined owner snapshot")
    expected = constructor(definition, row.get("level"), receipt.get("owner_stats"))
    stored = dict(
        receipt,
        characteristics={
            int(k): v for k, v in receipt.get("characteristics", {}).items()
        },
    )
    if stored != expected:
        raise ValueError("Changed native faW combined owner snapshot")
    return expected
