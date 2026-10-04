"""13560/cvZ EFFECT_UNAPPLICATION for an owned running-effect UID.

Native cjM -> aVz locates target.drJ().dk(uid), updates that running effect
from its iN payload, then removes it through Qf.q. Keep the original owned
ProtoRunningEffect bytes: an empty/minimal proto would overwrite runtime
UID/value/caster/target. The ledger decides whether removal is valid.
"""
import struct

EFFECT_UNAPPLICATION_OPCODE = 13560
STATE_CARRIER_EFFECT_CLASS = 310  # eVi.rpJ -> eZk, distinct from apply304/eWu.


def _read_varint(data, offset):
    result = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise ValueError("Truncated running-effect protobuf")
        byte = data[offset]
        offset += 1
        if shift == 63 and byte > 1:
            raise ValueError("Invalid running-effect protobuf varint")
        result |= (byte & 127) << shift
        if not byte & 128:
            return result, offset
    raise ValueError("Invalid running-effect protobuf varint")


def _identity_fields(data, *, integer_fields=(1, 2, 3, 4, 6, 7), messages=None):
    fields, offset = {}, 0
    while offset < len(data):
        tag, offset = _read_varint(data, offset)
        field, wire = tag >> 3, tag & 7
        if not field:
            raise ValueError("Invalid running-effect protobuf field")
        if wire == 0:
            value, offset = _read_varint(data, offset)
            if field in integer_fields:
                if field in fields:
                    raise ValueError("Duplicate running-effect identity/value field")
                fields[field] = value
        elif wire == 2:
            length, offset = _read_varint(data, offset)
            if messages is not None and field == 8:
                if field in messages:
                    raise ValueError("Duplicate running-effect AdditionalDatas")
                messages[field] = data[offset : offset + length]
            offset += length
        elif wire in (1, 5):
            offset += 8 if wire == 1 else 4
        else:
            raise ValueError("Unsupported running-effect protobuf wire type")
        if offset > len(data):
            raise ValueError("Truncated running-effect protobuf")
    return fields


def running_effect_removal(
    fight_id,
    action_id,
    *,
    effect_class,
    target_id,
    uid,
    running_effect_payload,
    sequence=-1
):
    """Encode native removal using the complete payload owned by this fight.

    The outer actor is the target whose running-effect manager owns uid;
    it need not be the caster. Native sequence -1 means no explicit sequence.
    """
    if any(
        type(value) is not int or not 0 < value < (1 << 31)
        for value in (fight_id, action_id, effect_class)
    ):
        raise ValueError("Invalid removal fight/action/effect class")
    if type(sequence) is not int or not -1 <= sequence < (1 << 31):
        raise ValueError("Invalid removal sequence")
    if type(uid) is not int or not 0 < uid < (1 << 63):
        raise ValueError("Invalid owned running-effect UID")
    if (
        type(target_id) is not int
        or target_id == 0
        or not -(1 << 63) <= target_id < (1 << 63)
    ):
        raise ValueError("Invalid owned removal target")
    if (
        not isinstance(running_effect_payload, bytes)
        or not 0 < len(running_effect_payload) <= 32767
    ):
        raise ValueError("Missing or oversized original running-effect payload")
    messages = {}
    fields = _identity_fields(running_effect_payload, messages=messages)
    if not {1, 2, 3, 4, 6, 7} <= fields.keys():
        raise ValueError("Incomplete original running-effect payload")
    if fields[1] != uid or fields[7] != target_id & ((1 << 64) - 1):
        raise ValueError("Running-effect payload identity differs from removal")
    if effect_class == STATE_CARRIER_EFFECT_CLASS:
        if 8 not in messages:
            raise ValueError("State carrier310 is missing original AdditionalDatas")
        state_fields = _identity_fields(messages[8], integer_fields=(13,))
        if state_fields.get(13) != uid:
            raise ValueError("State carrier AdditionalDatas UID differs from removal")
    generic_valid = 0 < fields[3] < (1 << 31)
    if effect_class == STATE_CARRIER_EFFECT_CLASS and fields[3] == (1 << 64) - 1:
        generic_valid = True  # eZR.bcc -> eVJ(-1) for a standalone native carrier.
    if not generic_valid or fields[6] == 0:
        raise ValueError("Missing owned effect/caster identity in original payload")
    return (
        struct.pack(
            ">iiiih",
            fight_id,
            action_id,
            sequence,
            effect_class,
            len(running_effect_payload),
        )
        + running_effect_payload
        + struct.pack(">qq", target_id, uid)
    )
