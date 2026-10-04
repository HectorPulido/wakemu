"""Owned eXs value packet; evaluated healing is HP + virtual HP gained.

Native eXs.fOz updates aSg after discarding overflow. Qe.bca serializes that
value; eXs does not override AdditionalDatas serialization.
"""
import struct
from .combat_effects import _integer
from .combat_damage_healing import HEAL_ELEMENTS


def direct_healing(
    fight_id,
    action_id,
    *,
    uid,
    generic_effect,
    effect_class,
    caster_id,
    target_id,
    restored,
    base_uid=None,
    sequence=-1
):
    if base_uid is None:
        base_uid = uid
    if effect_class not in HEAL_ELEMENTS:
        raise ValueError("Unknown native healing effect class")
    if any(
        type(v) is not int or not 0 < v < 1 << 31
        for v in (fight_id, action_id, generic_effect)
    ):
        raise ValueError("Invalid native healing fight/action/effect")
    if type(restored) is not int or not 0 <= restored < 1 << 31:
        raise ValueError("Invalid actual native healing value")
    if (
        type(uid) is not int
        or not 0 < uid < 1 << 63
        or type(base_uid) is not int
        or not 0 <= base_uid < 1 << 63
    ):
        raise ValueError("Invalid owned healing UID")
    if type(sequence) is not int or not -1 <= sequence < 1 << 31:
        raise ValueError("Invalid healing sequence")
    if any(
        type(v) is not int or v == 0 or not -(1 << 63) <= v < 1 << 63
        for v in (caster_id, target_id)
    ):
        raise ValueError("Missing owned healing actor")
    payload = b"".join(
        _integer(k, v)
        for k, v in (
            (1, uid),
            (2, base_uid),
            (3, generic_effect),
            (4, restored),
            (6, caster_id),
            (7, target_id),
        )
    )
    return (
        struct.pack(
            ">iiiBih", fight_id, action_id, sequence, 0, effect_class, len(payload)
        )
        + payload
    )
