"""Native owned eZk310 carrier, distinct from its eWu304 applying parent.

Wire proof: ProbeStateCarrier.java native eZk.a/bca; cvY13497/cjL applies
an already evaluated running effect. Scheduling values remain explicit native
inputs rather than inferred turns; server clock policy belongs to the ledger.
"""
import struct
from .combat_effects import _integer, _varint
from .combat_effect_removal import running_effect_removal, STATE_CARRIER_EFFECT_CLASS

STATE_CARRIER_APPLICATION_OPCODE = 13497


def state_carrier_payload(
    *,
    uid,
    base_uid,
    caster_id,
    target_id,
    state_id,
    level,
    native_turn_clock,
    native_realtime_remaining,
    generic_effect=-1,
    related_uid=0,
    flag17=False,
    flag18=False,
    critical=False,
    timing_payload=None
):
    """iN plus ij AdditionalDatas matching native eZk.b/iN serialization.

    Additional10 is fyW.ae(state,level);13 is the carrier UID;21=rHv;
    22=rIY;50=dPa. A parent apply UID must never replace Additional13.
    timing_payload, when supplied, is the caller's audited iB TimeDatas.
    """
    for identity in (uid,):
        if type(identity) is not int or not 0 < identity < (1 << 63):
            raise ValueError("Invalid owned state carrier UID")
    if base_uid is None:
        base_uid = uid
    if any(
        type(value) is not int or not 0 <= value < (1 << 63)
        for value in (base_uid, related_uid)
    ):
        raise ValueError("Invalid native carrier base/related UID")
    if uid == related_uid:
        raise ValueError("State carrier UID must be distinct from related UID")
    if any(
        type(value) is not int or value == 0 or not -(1 << 63) <= value < (1 << 63)
        for value in (caster_id, target_id)
    ):
        raise ValueError("Invalid owned state carrier actor")
    if (
        type(state_id) is not int
        or not 0 < state_id <= 32767
        or type(level) is not int
        or not 0 <= level <= 32767
    ):
        raise ValueError("State identity/level outside native signed shorts")
    if type(generic_effect) is not int or not (
        generic_effect == -1 or 0 < generic_effect < (1 << 31)
    ):
        raise ValueError("Invalid carrier generic effect")
    if type(native_turn_clock) is not int or not -1 <= native_turn_clock < (1 << 63):
        raise ValueError("Invalid explicit native carrier turn clock")
    # eZk.a initializes rIY directly from fyW.guH; native permanent
    # Sacrier3702 has -1000, not a normalized -1 sentinel.
    if type(native_realtime_remaining) is not int or not -(
        1 << 63
    ) <= native_realtime_remaining < (1 << 63):
        raise ValueError("Invalid explicit native carrier realtime clock")
    if any(type(value) is not bool for value in (flag17, flag18, critical)):
        raise ValueError("Invalid native carrier flags")
    if timing_payload is not None and not isinstance(timing_payload, bytes):
        raise ValueError("Native TimeDatas must be bytes")
    packed = (state_id << 16) | level
    payload = b"".join(
        _integer(k, v)
        for k, v in [
            (1, uid),
            (2, base_uid),
            (3, generic_effect),
            (4, packed),
            (6, caster_id),
            (7, target_id),
        ]
    )
    additional = b"".join(
        _integer(k, v)
        for k, v in [
            (10, packed),
            (13, uid),
            (17, int(flag17)),
            (18, int(flag18)),
            (19, int(critical)),
            (21, native_turn_clock),
            (22, native_realtime_remaining),
            (50, related_uid),
        ]
    )
    payload += b"\x42" + _varint(len(additional)) + additional
    if timing_payload is not None:
        payload += b"\x5a" + _varint(len(timing_payload)) + timing_payload
    return payload


def state_carrier_application(
    fight_id, action_id, *, uid, target_id, running_effect_payload, sequence=-1
):
    """13497/cvY application of an owned carrier310 with synchronized UID."""
    validated = running_effect_removal(
        fight_id,
        action_id,
        effect_class=STATE_CARRIER_EFFECT_CLASS,
        uid=uid,
        target_id=target_id,
        running_effect_payload=running_effect_payload,
        sequence=sequence,
    )
    return validated[:-16]  # cvY has cvZ's exact prefix/proto, without removal IDs.
