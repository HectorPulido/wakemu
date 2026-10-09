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
            if messages is not None and field in (5, 8):
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


def _proto_replace(data, field, wire, replacement):
    """Preserve every unrelated field while replacing one native protobuf field."""
    result, offset, found = bytearray(), 0, False
    while offset < len(data):
        start = offset
        tag, offset = _read_varint(data, offset)
        kind = tag & 7
        if kind == 0:
            _, offset = _read_varint(data, offset)
        elif kind == 2:
            length, offset = _read_varint(data, offset)
            offset += length
        elif kind in (1, 5):
            offset += 8 if kind == 1 else 4
        else:
            raise ValueError("Unsupported protobuf wire type")
        if offset > len(data):
            raise ValueError("Truncated protobuf field")
        if tag >> 3 == field:
            if found or kind != wire:
                raise ValueError("Duplicate or invalid protobuf field")
            found = True
            result.extend(replacement)
        else:
            result.extend(data[start:offset])
    if not found:
        result.extend(replacement)
    return bytes(result)


def state_unapplication_payload(payload):
    # eZR.f(iB) reads field1 NotifyUnapplicationForced into rIZ; aVz.cbj
    # requires eZR.fMV() before Qf.q. Evaluated eZk has aZN/bbW false.
    from .combat_effects import _varint

    timing = None
    offset = 0
    while offset < len(payload):
        tag, offset = _read_varint(payload, offset)
        wire = tag & 7
        if wire == 0:
            _, offset = _read_varint(payload, offset)
        elif wire == 2:
            length, offset = _read_varint(payload, offset)
            if tag >> 3 == 11:
                if timing is not None:
                    raise ValueError("Duplicate TimeDatas")
                timing = payload[offset : offset + length]
            offset += length
        elif wire in (1, 5):
            offset += 8 if wire == 1 else 4
        else:
            raise ValueError("Unsupported protobuf wire type")
    timing = _proto_replace(timing or b"", 1, 0, b"\x08\x01")
    return _proto_replace(payload, 11, 2, b"\x5a" + _varint(len(timing)) + timing)


def running_effect_removal(
    fight_id,
    action_id,
    *,
    effect_class,
    target_id,
    uid,
    running_effect_payload,
    sequence=-1,
    notify_unapplication=True,
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
    from .combat_subscription_runners import GROUP_SUBSCRIPTION_FAMILIES
    from .combat_delivery_owners import owner_catalog

    owner_contract = owner_catalog()["effects"].get(str(effect_class))
    configured_area = (
        isinstance(owner_contract, dict) and owner_contract.get("runner") == "eYQ"
    )
    if configured_area:
        actor_mode, cell_mode = owner_contract.get("bbA"), owner_contract.get("bbB")
        if type(actor_mode) is not bool or type(cell_mode) is not bool:
            raise ValueError("Missing native configured-area removal owner contract")
        if (7 in fields and not actor_mode) or (7 not in fields and not cell_mode):
            raise ValueError(
                "Native configured-area removal recipient violates owner flags"
            )

    cell_only = (
        effect_class in (315, 402)
        or (configured_area and 7 not in fields)
        or (effect_class == 935 and 7 not in fields)
        or (7 not in fields and effect_class in GROUP_SUBSCRIPTION_FAMILIES)
    )
    required = {1, 2, 3, 4, 6} if cell_only else {1, 2, 3, 4, 6, 7}
    if not required <= fields.keys():
        raise ValueError("Incomplete original running-effect payload")
    # Qe cell-only branch registers on bfr.bax(), with bfs=null. Its manager
    # owner is caster6; inventing target7 would alter native cell identity.
    owner = fields[6] if cell_only else fields[7]
    if cell_only and (
        5 not in messages
        or 7 in fields
        # eYQ serializes its area reference as Qe value, not zero.
        or (not configured_area and effect_class != 935 and fields[4] != 0)
    ):
        raise ValueError("Native cell null payload must have absent target/zero value")
    if cell_only:
        position = _identity_fields(messages[5], integer_fields=(1, 2, 3))
        if set(position) != {1, 2, 3}:
            raise ValueError("Native cell null position is incomplete")
        values = [
            v - (1 << 64) if v >= (1 << 63) else v
            for v in (position[k] for k in (1, 2, 3))
        ]
        if (
            any(not -(1 << 31) <= v < (1 << 31) for v in values[:2])
            or not -32768 <= values[2] < 32768
        ):
            raise ValueError(
                "Native cell null position exceeds native coordinate bounds"
            )
    if fields[1] != uid or owner != target_id & ((1 << 64) - 1):
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
    if effect_class in (STATE_CARRIER_EFFECT_CLASS, 649, 933) and notify_unapplication:
        # aVz requires fMV before Qf.q. These authoritative book/carrier
        # removals must carry iB1 even when PK has no subscriptions or delay.
        running_effect_payload = state_unapplication_payload(running_effect_payload)
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
