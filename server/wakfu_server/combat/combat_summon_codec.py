"""eZl/eZm307 complete native vJ/wU/SQ additional data.

The caller supplies the authoritative descriptor obstacle byte identity. Runtime effect
UID and creature UID are distinct and both preserved. No NPC format2 is used.
"""
import struct
from .combat_summon import SummonSpecification, summon_additional_payload
from .combat_effects import _integer, _varint
from .combat_displacement import position_payload
from .combat_running_context import running_context_payload


def summon_descriptor_blob(
    specification, *, actor_id, caster_id, obstacle_index, properties
):
    if (
        not isinstance(specification, SummonSpecification)
        or type(caster_id) is not int
        or caster_id == 0
        or not -(1 << 63) <= caster_id < 1 << 63
        or type(obstacle_index) is not int
        or not -128 <= obstacle_index <= 127
    ):
        raise ValueError("Missing eHD summon descriptor identities")
    summon_additional_payload(actor_id)
    properties = tuple(properties)
    if (
        len(properties) > 65535
        or len(properties) != len(set(properties))
        or any(type(p) is not int or not 0 <= p < 128 for p in properties)
    ):
        raise ValueError("Invalid native eHN property list")
    # eHD(short reference,"",-1,short level): vJ null vK/vM and pRNN=-1.
    descriptor = struct.pack(
        ">hHiqhBBBiqB",
        specification.reference,
        0,
        -1,
        actor_id,
        specification.level,
        obstacle_index & 255,
        0,
        0,
        specification.direction,
        -1,
        0,
    )
    property_blob = struct.pack(">H", len(properties)) + b"".join(
        struct.pack(">BB", p, 1) for p in properties
    )
    anchor = {"current": 0, "start": 1, "caster": 2}[specification.timeline_anchor]
    return (
        bytes([int(specification.self_controlled)])
        + descriptor
        + property_blob
        + struct.pack(
            ">BqiB",
            anchor,
            caster_id,
            specification.timeline_offset,
            specification.team,
        )
    )


def summon_payload(
    *,
    uid,
    base_uid,
    effect_reference,
    caster_id,
    cell,
    specification,
    actor_id,
    obstacle_index,
    properties,
    timing_payload,
    status=-1,
    container_type=None,
    container_id=None,
    context_payload=None,
    running_value=None
):
    if base_uid is None:
        base_uid = uid
    if (
        type(uid) is not int
        or not 0 < uid < 1 << 63
        or type(base_uid) is not int
        or not 0 <= base_uid < 1 << 63
        or type(effect_reference) is not int
        or not 0 < effect_reference < 1 << 31
        or not isinstance(timing_payload, bytes)
        or type(status) is not int
        or not -128 <= status <= 127
    ):
        raise ValueError("Unknown native summon running effect/timing")
    if running_value is None:
        running_value = specification.reference
    if type(running_value) is not int or not -(1 << 31) <= running_value < (1 << 31):
        raise ValueError("Native summon runner value requires signed int")
    blob = summon_descriptor_blob(
        specification,
        actor_id=actor_id,
        caster_id=caster_id,
        obstacle_index=obstacle_index,
        properties=properties,
    )
    body = b"".join(
        _integer(k, v)
        for k, v in (
            (1, uid),
            (2, base_uid),
            (3, effect_reference),
            (4, running_value),
            (6, caster_id),
        )
    )
    position = position_payload(cell)
    body += b"\x2a" + _varint(len(position)) + position
    additional = b"\x0a" + _varint(len(blob)) + blob  # ij.bT raw fj bytes.
    body += b"\x42" + _varint(len(additional)) + additional
    timing = timing_payload + _integer(2, status) + _integer(5, 1)
    body += b"\x5a" + _varint(len(timing)) + timing
    return (
        body
        + summon_additional_payload(actor_id)
        + running_context_payload(
            container_type=container_type,
            container_id=container_id,
            context_payload=context_payload,
        )
    )


def summon_application(fight_id, action_id, **kwargs):
    if any(type(i) is not int or not 0 < i < 1 << 31 for i in (fight_id, action_id)):
        raise ValueError("Invalid native summon fight/action")
    body = summon_payload(**kwargs)
    if len(body) > 32767:
        raise ValueError("Native summon effect exceeds cvY short size")
    from .combat_entity_creation_delivery import immediate_entity_creation

    return immediate_entity_creation(fight_id, action_id, 307, body)
