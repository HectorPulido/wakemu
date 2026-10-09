"""Native eWB carry gate and eZE additional payload, independent of QI mutation."""
from .combat_displacement import position_payload
from .combat_effects import _integer, _varint


def native_throw_additional(target_cell, qcl):
    """eZE.b(iP) writes bft (not rDV) and explicit private qcl."""
    if type(qcl) is not bool:
        raise ValueError("Missing native eZE private qcl authority")
    position = position_payload(target_cell)
    return (
        _varint(15 << 3 | 2)
        + _varint(len(position))
        + position
        + _integer(17, int(qcl))
    )


def native_carry_gate(
    *,
    target_is_ehh,
    caster_is_ehg,
    both_are_ehg_affiliations,
    target_cannot_be_carried,
    target_stabilized,
    bypass_stabilization,
    caster_enemy_stabilized,
    target_enemy_stabilized,
    caster_ally_stabilized,
    target_ally_stabilized,
    same_affiliation
):
    """Exact eWB.c early guards; carrier.a(eHH) owns remaining eligibility."""
    flags = locals()
    if any(type(value) is not bool for value in flags.values()):
        raise ValueError("Missing typed native eWB carry guard facts")
    if not target_is_ehh or not caster_is_ehg or target_cannot_be_carried:
        return False
    if not bypass_stabilization:
        if target_stabilized:
            return False
        if both_are_ehg_affiliations:
            enemy = caster_enemy_stabilized or target_enemy_stabilized
            ally = caster_ally_stabilized or target_ally_stabilized
            target_permits_carry = not target_cannot_be_carried
            if not same_affiliation and (enemy or not target_permits_carry):
                return False
            if same_affiliation and (ally or not target_permits_carry):
                return False
    return True


def native_carry_payload(
    *,
    uid,
    base_uid,
    reference,
    family,
    caster_id,
    target_id,
    cell,
    value,
    qcl,
    timing_payload,
    context_payload
):
    """Fresh eWB/eZE Qe.bca with explicit PS serialization authority."""
    from .combat_running_container import running_container_payload
    from .combat_running_context import running_context_payload

    if (
        family not in (333, 334)
        or type(uid) is not int
        or not 0 < uid < 1 << 63
        or type(reference) is not int
        or not 0 < reference < 1 << 31
        or type(caster_id) is not int
        or caster_id == 0
        or not -(1 << 63) <= caster_id < 1 << 63
        or type(value) is not int
        or not -(1 << 31) <= value < 1 << 31
        or not isinstance(timing_payload, bytes)
    ):
        raise ValueError("Missing actual native carry delivery identity/clocks")
    base_uid = uid if base_uid is None else base_uid
    if type(base_uid) is not int or not 0 <= base_uid < 1 << 63:
        raise ValueError("Invalid actual native carry base UID")
    if target_id is not None and (
        type(target_id) is not int
        or target_id == 0
        or not -(1 << 63) <= target_id < 1 << 63
    ):
        raise ValueError("Invalid actual native carry PV identity")
    if family == 334 and target_id is None:
        raise ValueError("Native carry requires its actual target PV")
    position = position_payload(cell)
    payload = b"".join(
        _integer(k, v) for k, v in ((1, uid), (2, base_uid), (3, reference), (4, value))
    )
    payload += _varint(5 << 3 | 2) + _varint(len(position)) + position
    payload += _integer(6, caster_id)
    if target_id is not None:
        payload += _integer(7, target_id)
    if family == 333:
        additional = native_throw_additional(cell, qcl)
        payload += _varint(8 << 3 | 2) + _varint(len(additional)) + additional
    payload += running_container_payload()
    # Actual fresh eZR constructor is -1, and neither eWB/eZE calls fc.
    clocks = timing_payload + _integer(2, -1) + _integer(5, 1)
    payload += _varint(11 << 3 | 2) + _varint(len(clocks)) + clocks
    payload += running_context_payload(context_payload=context_payload)
    return payload


def native_carry_packet(fight_id, action_id, payload, *, family, sequence=-1):
    """Actual evaluated cvX/eIK=false, preserving nullable iN target."""
    import struct

    if (
        family not in (333, 334)
        or not isinstance(payload, bytes)
        or not 0 < len(payload) <= 32767
        or any(
            type(v) is not int or not -(1 << 31) <= v < 1 << 31
            for v in (fight_id, action_id, sequence)
        )
    ):
        raise ValueError("Invalid native carry application packet")
    return (
        12613,
        struct.pack(">iiiBih", fight_id, action_id, sequence, 0, family, len(payload))
        + payload,
    )
