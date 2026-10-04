"""Audited native Xelor6755 initialization; turn triggers remain server-owned.

eWn/class649 creates spell UID equal to reference (not character<<32).
The full passive also has triggered effects; this module does not omit them
by pretending that initialization alone implements the entire passive.
"""
import struct
from .combat_effects import _integer, _varint

INITIAL_SPELLS = ((313107, 5345, 0), (313108, 3909, 1), (349284, 7794, 2))


def unlock_packet(
    fight_id, action_id, *, uid, actor_id, generic_effect, spell_id, slot
):
    if (generic_effect, spell_id, slot) not in INITIAL_SPELLS:
        raise ValueError("Unknown native Xelor initialization spell")
    if (
        type(uid) is not int
        or not 0 < uid < (1 << 63)
        or type(actor_id) is not int
        or not 0 < actor_id < (1 << 63)
    ):
        raise ValueError("Missing owned effect or player identifier")
    payload = b"".join(
        _integer(k, v)
        for k, v in (
            (1, uid),
            (2, 0),
            (3, generic_effect),
            (4, 0),
            (6, actor_id),
            (7, actor_id),
        )
    )
    # Native eWn.b(iP): il.ek/ref, en/-1, ep/tab2, eq/slot.
    additional = b"".join(
        _integer(k, v) for k, v in ((10, spell_id), (14, -1), (19, 2), (20, slot))
    )
    payload += _varint(66) + _varint(len(additional)) + additional
    return (
        struct.pack(">iiiBih", fight_id, action_id, -1, 0, 649, len(payload)) + payload
    )


def initial_spell_unlocks(
    character,
    fight_id,
    action_id,
    *,
    effect_uid,
    has_action933,
    instance_id,
    passive6755_applied
):
    """Native special spells after6755 application, guarded by real criteria.

     Caller must schedule this at native combat initialization and run remaining
    6755 triggers. Returned spellUIDs must be authorized by server cast handling.
    """
    if character["breed"] != 5:
        raise ValueError("Xelor passive belongs to breed5")
    if type(has_action933) is not bool or type(instance_id) is not int:
        raise ValueError("Authoritative initialization conditions required")
    if passive6755_applied is not True:
        raise ValueError("Native passive6755 must already be installed")
    actor = character["id"]
    packets = []
    if has_action933 or instance_id == 862:
        return dict(packets=packets, special_spells=[])
    for index, (generic, spell, slot) in enumerate(INITIAL_SPELLS, 1):
        packets.append(
            (
                12613,
                unlock_packet(
                    fight_id,
                    action_id,
                    uid=effect_uid + index,
                    actor_id=actor,
                    generic_effect=generic,
                    spell_id=spell,
                    slot=slot,
                ),
            )
        )
    return dict(
        packets=packets,
        special_spells=[
            dict(id=spell, uid=spell, level=character["level"], slot=slot)
            for _, spell, slot in INITIAL_SPELLS
        ],
    )
