"""Original eZs324 float factors, captured vJ descriptor and selected slot/SQ."""
from dataclasses import dataclass
import struct
from .combat_captured_summon import CapturedSummonPlan
from .combat_effects import _integer, _varint
from .combat_displacement import position_payload
from .combat_running_context import running_context_payload
from .combat_summon import summon_additional_payload


@dataclass(frozen=True)
class CapturedDescriptor:
    minimum_hp: int
    owner_id: int
    direction: int
    from_symbiot: bool


def captured_descriptor_blob(plan, descriptor, *, obstacle_index, caster_id):
    if (
        not isinstance(plan, CapturedSummonPlan)
        or not plan.allowed
        or plan.specification is None
    ):
        raise ValueError("Missing actual selected captured summon plan")
    if not isinstance(descriptor, CapturedDescriptor):
        raise ValueError("Missing actual captured eHD descriptor fields")
    for value, bits in (
        (descriptor.minimum_hp, 32),
        (descriptor.owner_id, 64),
        (descriptor.direction, 32),
        (caster_id, 64),
        (obstacle_index, 8),
        (plan.selected_slot, 8),
    ):
        if type(value) is not int or not -(1 << (bits - 1)) <= value < (
            1 << (bits - 1)
        ):
            raise ValueError("Invalid signed native captured descriptor field")
    if caster_id != plan.owner_id or descriptor.owner_id != plan.owner_id:
        raise ValueError("Captured descriptor owner differs from actual caster")
    if type(descriptor.from_symbiot) is not bool or not isinstance(plan.name, str):
        raise ValueError("Missing captured descriptor name/source")
    summon_additional_payload(plan.actor_id)
    name = plan.name.encode("utf-8")
    if len(name) > 65535:
        raise ValueError("Captured descriptor name exceeds native length")
    spec = plan.specification
    try:
        vj = struct.pack(">hH", spec.reference, len(name)) + name
        vj += struct.pack(
            ">iqhbBBiqB",
            descriptor.minimum_hp,
            plan.actor_id,
            spec.level,
            obstacle_index,
            0,
            0,
            descriptor.direction,
            descriptor.owner_id,
            descriptor.from_symbiot,
        )
        anchor = {"current": 0, "start": 1, "caster": 2}[spec.timeline_anchor]
        return (
            struct.pack(">ff", plan.main_factor, plan.secondary_factor)
            + vj
            + struct.pack(
                ">bBqi", plan.selected_slot, anchor, caster_id, spec.timeline_offset
            )
        )
    except (struct.error, KeyError, OverflowError) as error:
        raise ValueError("Invalid native captured descriptor/SQ fields") from error


def captured_summon_payload(
    *,
    plan,
    descriptor,
    uid,
    base_uid,
    effect_reference,
    caster_id,
    cell,
    obstacle_index,
    timing_payload,
    status=-1,
    container_type=None,
    container_id=None,
    context_payload=None,
    running_value=0
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
        or type(running_value) is not int
        or not -(1 << 31) <= running_value < 1 << 31
        or type(status) is not int
        or not -128 <= status <= 127
        or not isinstance(timing_payload, bytes)
    ):
        raise ValueError("Unknown native captured runner/timing")
    blob = captured_descriptor_blob(
        plan, descriptor, obstacle_index=obstacle_index, caster_id=caster_id
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
    additional = b"\x0a" + _varint(len(blob)) + blob
    body += b"\x42" + _varint(len(additional)) + additional
    timing = timing_payload + _integer(2, status) + _integer(5, 1)
    body += b"\x5a" + _varint(len(timing)) + timing
    return (
        body
        + summon_additional_payload(plan.actor_id)
        + running_context_payload(
            container_type=container_type,
            container_id=container_id,
            context_payload=context_payload,
        )
    )


def captured_summon_application(fight_id, action_id, **kwargs):
    if any(
        type(value) is not int or not 0 < value < 1 << 31
        for value in (fight_id, action_id)
    ):
        raise ValueError("Invalid native captured fight/action")
    body = captured_summon_payload(**kwargs)
    if len(body) > 32767:
        raise ValueError("Native captured effect exceeds cvY short size")
    from .combat_entity_creation_delivery import immediate_entity_creation

    return immediate_entity_creation(fight_id, action_id, 324, body)
