"""Native configured eYQ codec; does not imply effect-area lifecycle support."""
import struct
from .combat_effects import _integer, _varint
from .combat_displacement import position_payload
from .combat_running_context import running_context_payload
from wakfu_server.wire import proto_fields, proto_field


def area_payload(
    *,
    uid,
    base_uid,
    effect_reference,
    area_reference,
    area_uid,
    level,
    keep_after,
    direction,
    caster_id,
    cell,
    timing_payload,
    status=-1,
    container_type=None,
    container_id=None,
    context_payload=None,
    target_id=None
):
    if base_uid is None:
        base_uid = uid
    if (
        any(
            type(v) is not int or not 0 < v < 1 << 63 for v in (uid, base_uid, area_uid)
        )
        or any(
            type(v) is not int or not 0 < v < 1 << 31
            for v in (effect_reference, area_reference)
        )
        or type(level) is not int
        or not -32768 <= level <= 32767
        or type(keep_after) is not bool
        or (
            direction is not None
            and (type(direction) is not int or not 0 <= direction <= 7)
        )
        or type(caster_id) is not int
        or not -(1 << 63) <= caster_id < 1 << 63
        or (
            target_id is not None
            and (type(target_id) is not int or not -(1 << 63) <= target_id < 1 << 63)
        )
        or type(status) is not int
        or not -128 <= status <= 127
        or not isinstance(timing_payload, bytes)
    ):
        raise ValueError("Missing native eYQ area identity or execution context")
    body = b"".join(
        _integer(k, v)
        for k, v in (
            (1, uid),
            (2, base_uid),
            (3, effect_reference),
            (4, area_reference),
        )
    )
    position = position_payload(cell)
    body += b"\x2a" + _varint(len(position)) + position
    if caster_id:
        body += _integer(6, caster_id)
    if target_id is not None:
        body += _integer(7, target_id)
    # eYQ.b(iP): level14, orientation16 (null=-1), keep17, area UID21.
    additional = b"".join(
        _integer(k, v)
        for k, v in (
            (14, level),
            (16, -1 if direction is None else direction),
            (17, int(keep_after)),
            (21, area_uid),
        )
    )
    body += b"\x42" + _varint(len(additional)) + additional
    clock = dict(proto_fields(timing_payload))
    clock[16] = status & ((1 << 64) - 1)
    clock[40] = 1
    timing = b"".join(proto_field(tag, clock[tag]) for tag in sorted(clock))
    body += b"\x5a" + _varint(len(timing)) + timing
    return body + running_context_payload(
        container_type=container_type,
        container_id=container_id,
        context_payload=context_payload,
    )


def area_application(
    fight_id, action_id, *, effect_class=315, execute_immediate=False, **kwargs
):
    from .combat_delivery_owners import owner_catalog

    row = owner_catalog()["effects"].get(str(effect_class))
    if (
        type(effect_class) is not int
        or not isinstance(row, dict)
        or row.get("runner") not in ("eYQ", "eYS", "eYU", "eYW")
    ):
        raise ValueError("Unknown native eYQ packet family")
    if kwargs.get("target_id") is not None and row.get("bbA") is not True:
        raise ValueError("Native eYQ packet recipient violates owner flags")
    if any(type(i) is not int or not 0 < i < 1 << 31 for i in (fight_id, action_id)):
        raise ValueError("Invalid native area fight/action")
    if type(execute_immediate) is not bool:
        raise ValueError("Missing native area delivery execution policy")
    body = area_payload(**kwargs)
    if len(body) > 32767:
        raise ValueError("Native area effect exceeds cvY short size")
    if execute_immediate:
        from .combat_entity_creation_delivery import immediate_entity_creation

        return immediate_entity_creation(fight_id, action_id, effect_class, body)
    return (
        13497,
        struct.pack(">iiiih", fight_id, action_id, -1, effect_class, len(body)) + body,
    )


def area_retirement(fight_id, action_id, area_uid):
    """Native13726 cvE/cjp/aTW retires one actual Qs area and its visuals."""
    if (
        any(
            type(value) is not int or not 0 < value < 1 << 31
            for value in (fight_id, action_id)
        )
        or type(area_uid) is not int
        or not 0 < area_uid < 1 << 63
    ):
        raise ValueError("Invalid native area retirement identity")
    return 13726, struct.pack(">iiiq", fight_id, action_id, -1, area_uid)
