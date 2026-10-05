"""Current-client cvX direct running-effect encoder with owned actor identifiers.

The caller supplies authoritative post-mitigation damage; selecting conditional
spell effect branches and computing mitigation belongs to the combat engine.
"""
import struct
from .combat_damage_healing import DAMAGE_FAMILIES

# Native bdata group children, normal variants. This is identification, not a
# blanket promise that each conditional branch applies to every cast.
OUGINAK_BASE_DAMAGE = {6260: (339483, 4), 6261: (241232, 3), 6266: (339524, 5)}


def _varint(value):
    value &= (1 << 64) - 1
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def _integer(field, value):
    return _varint(field << 3) + _varint(value)


def direct_damage(
    fight_id,
    action_id,
    *,
    uid,
    generic_effect,
    element,
    caster_id,
    target_id,
    damage,
    sequence=-1,
    base_uid=None,
    armor_absorbed=0,
    barrier_absorbed=0
):
    """12613/cvX with iN ProtoRunningEffect for eXt classes1..5.

    Negative target IDs are valid owned NPC IDs. No captured actor/effect IDs
    are copied. None selects the native fresh-effect base UID (its own UID).
    """
    if base_uid is None:
        base_uid = uid
    if type(base_uid) is not int or not 0 <= base_uid < (1 << 63):
        raise ValueError("Invalid native damage base UID")
    if element not in DAMAGE_FAMILIES:
        raise ValueError("Unknown native damage element")
    if (
        type(damage) is not int
        or not 0 <= damage < (1 << 31)
        or not 0 < generic_effect < (1 << 31)
        or not 0 < uid < (1 << 63)
    ):
        raise ValueError("Invalid authoritative damage/effect identifier")
    if any(
        type(identity) is not int
        or not -(1 << 63) <= identity < (1 << 63)
        or identity == 0
        for identity in (caster_id, target_id)
    ):
        raise ValueError("Missing owned actor identifier")
    if any(
        type(value) is not int or not 0 <= value < (1 << 31)
        for value in (armor_absorbed, barrier_absorbed)
    ):
        raise ValueError("Invalid authoritative absorbed damage")
    payload = b"".join(
        _integer(k, v)
        for k, v in (
            (1, uid),
            (2, base_uid),
            (3, generic_effect),
            (4, damage),
            (6, caster_id),
            (7, target_id),
        )
    )
    # eXt.b/f: ij.getValue (10) is armor; ij.Mg (19) is barrier.
    additional = _integer(10, armor_absorbed) + _integer(19, barrier_absorbed)
    payload += _varint((8 << 3) | 2) + _varint(len(additional)) + additional
    return (
        struct.pack(">iiiBih", fight_id, action_id, sequence, 0, element, len(payload))
        + payload
    )


def mp_loss(fight_id, action_id, *, uid, caster_id, target_id, amount, sequence=-1):
    """12613 native class48/eVZ, generic241233 (Ouginak6261 normal).

    Value is actual clamped loss. Bare native C() requests2 then resolves1;
    AdditionalDatas characId3 and originValue0 match eWW serialization.
    """
    if type(amount) is not int or not 0 <= amount <= 1 or not 0 < uid < (1 << 63):
        raise ValueError("Unsupported bare MP loss amount")
    if any(
        type(identity) is not int
        or not -(1 << 63) <= identity < (1 << 63)
        or identity == 0
        for identity in (caster_id, target_id)
    ):
        raise ValueError("Missing owned MP effect actor")
    payload = b"".join(
        _integer(k, v)
        for k, v in (
            (1, uid),
            (2, 0),
            (3, 241233),
            (4, amount),
            (6, caster_id),
            (7, target_id),
        )
    )
    additional = _integer(12, 3) + _integer(25, 0)
    payload += _varint((8 << 3) | 2) + _varint(len(additional)) + additional
    return (
        struct.pack(">iiiBih", fight_id, action_id, sequence, 0, 48, len(payload))
        + payload
    )
