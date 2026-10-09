"""Native null400 and eWQ/eWR current-characteristic family primitives.

Registry metadata identifies the family and fixed characteristic, never spell
IDs. eWN max-characteristic effects and dice/probability variants remain
separate unsupported paths. Native AdditionalDatas stores stat12/request25;
outer value4 stores actual applied delta, which is needed for exact removal.
"""
import math
from .combat_parameters import parameter_value
from wakfu_server.equipment_damage import _float
from .combat_effects import _integer, _varint
from .combat_effect_removal import running_effect_removal


def null_execution_status(parameters, *, current_status=-1):
    """eXE.C: param0@level0; no params preserve status (fresh eZR=-1).

    This graphical execution status is NOT the PT.bas success counter.
    """
    if len(parameters) % 2:
        raise ValueError("Invalid native parameter pairs")
    if type(current_status) is not int or not -128 <= current_status <= 127:
        raise ValueError("Invalid native current execution status")
    value = parameter_value(parameters, 0, 0) if parameters else current_status
    return ((value + 128) % 256) - 128


def stat_parameters(
    parameters, level, *, registered_stat_id, percent_default, trigger_value
):
    """eWW.C for1..3 parameter variants; dynamic stat from parameter2.

    Four parameters are dice (UK.d), five can include application chance.
    A value-1 copies the authoritative triggering value; resource-loss eWf
    specialization must already have been resolved by the caller.
    """
    if len(parameters) not in (2, 4, 6) or type(percent_default) is not bool:
        raise ValueError("Unsupported native current-stat parameter variant")
    values = [
        parameter_value(parameters, i, level) for i in range(len(parameters) // 2)
    ]
    value = values[0]
    if value == -1:
        if type(trigger_value) is not int:
            raise ValueError("Missing native triggering effect value")
        value = trigger_value
    stat = registered_stat_id
    if stat is None:
        if len(values) < 3:
            raise ValueError("Missing dynamic native characteristic")
        stat = values[2] & 255
    if type(stat) is not int or not 0 <= stat <= 255:
        raise ValueError("Invalid native characteristic registry ID")
    return dict(
        stat_id=stat,
        requested=value,
        percent=(values[1] == 1) if len(values) > 1 else percent_default,
    )


def current_stat_initial_eligible(requested, *, zero_initial_amount_rejected):
    """eWW.bbH checks evaluated amount BEFORE percent conversion/clamping.

    Passing this guard does not verify remaining native guards. Once execution
    reaches eZR.a/Qe.a, PT.bas increments regardless of postapply actual delta.
    """
    if type(requested) is not int or type(zero_initial_amount_rejected) is not bool:
        raise ValueError("Unknown native initial characteristic amount guard")
    return not (requested == 0 and zero_initial_amount_rejected)


def apply_current_stat(
    *,
    family,
    current,
    minimum,
    maximum,
    requested,
    percent,
    executable,
    frozen,
    source_guards_verified,
    limit_policy,
):
    """eWW.c -> eWQ.d/eWR.d; preserve prepercent request and actual delta."""
    if (
        family not in ("eWQ", "eWR")
        or any(
            type(v) is not int or not -(1 << 31) <= v < (1 << 31)
            for v in (current, minimum, maximum, requested)
        )
        or not minimum <= current <= maximum
    ):
        raise ValueError("Unsupported native current-characteristic snapshot")
    if limit_policy != "NORMAL":
        raise ValueError(
            "Native RESISTANCE_CAP requires owned-effect stack redistribution"
        )
    if (
        any(type(v) is not bool for v in (percent, executable, frozen))
        or source_guards_verified is not True
    ):
        raise ValueError("Unknown native current-stat application guards")
    evaluated = requested
    if percent and executable:
        evaluated = math.trunc(
            _float(_float(_float(current) / _float(100)) * _float(requested))
        )
    direction = 1 if family == "eWQ" else -1
    after = (
        current
        if frozen
        else max(minimum, min(maximum, current + direction * evaluated))
    )
    actual = (after - current) * direction
    return dict(
        current=after, actual=actual, requested=requested, stat_changed=after != current
    )


def remove_current_stat(
    *, family, current, minimum, maximum, actual, frozen, limit_policy
):
    """Inverse operation on OWNED actual delta, never requested/preclamp value."""
    return apply_current_stat(
        family="eWR" if family == "eWQ" else "eWQ" if family == "eWR" else "",
        current=current,
        minimum=minimum,
        maximum=maximum,
        requested=actual,
        percent=False,
        executable=True,
        frozen=frozen,
        source_guards_verified=True,
        limit_policy=limit_policy,
    )["current"]


def owned_effect_payload(
    *,
    uid,
    base_uid,
    generic_effect,
    caster_id,
    target_id,
    value,
    stat_id=None,
    requested=None,
    timing_payload=None,
    execution_status=None,
    executed=True,
    inherit_container=True,
):
    """Native iN for eXE or eWQ/eWR; explicit clocks supplied as TimeDatas.

    eXE has no stat AdditionalDatas; stat families require BOTH stat/request.
    No container reference or position is invented. Removal retains this exact
    payload so decoding cannot replace the owned UID or applied delta.
    """
    if base_uid is None:
        base_uid = uid
    if (
        type(uid) is not int
        or not 0 < uid < (1 << 63)
        or type(base_uid) is not int
        or not 0 <= base_uid < (1 << 63)
    ):
        raise ValueError("Invalid owned running-effect UID")
    if type(generic_effect) is not int or not 0 < generic_effect < (1 << 31):
        raise ValueError("Missing native generic effect identity")
    if (
        any(
            type(v) is not int or v == 0 or not -(1 << 63) <= v < (1 << 63)
            for v in (caster_id, target_id)
        )
        or type(value) is not int
        or not -(1 << 31) <= value < (1 << 31)
    ):
        raise ValueError("Invalid native actor/value identity")
    payload = b"".join(
        _integer(k, v)
        for k, v in (
            (1, uid),
            (2, base_uid),
            (3, generic_effect),
            (4, value),
            (6, caster_id),
            (7, target_id),
        )
    )
    if inherit_container:
        from .combat_running_container import running_container_payload

        payload += running_container_payload()
    if stat_id is not None or requested is not None:
        if (
            type(stat_id) is not int
            or not 0 <= stat_id <= 255
            or type(requested) is not int
            or not -(1 << 31) <= requested < (1 << 31)
        ):
            raise ValueError("Missing native stat AdditionalDatas")
        # Native em writes signed byte promoted to int (IDs>=128 become negative).
        native_stat = stat_id if stat_id < 128 else stat_id - 256
        additional = _integer(12, native_stat) + _integer(25, requested)
        payload += b"\x42" + _varint(len(additional)) + additional
    if timing_payload is not None and not isinstance(timing_payload, bytes):
        raise ValueError("Unknown native TimeDatas")
    if type(executed) is not bool:
        raise ValueError("Explicit native executed flag required")
    if execution_status is not None:
        if type(execution_status) is not int or not -128 <= execution_status <= 127:
            raise ValueError("Invalid native execution status byte")
        # eZR.QH: iB2=rIU status, iB5=rEj executed. Append overrides to
        # the same protobuf message while preserving native clock fields.
        timing_payload = (
            (b"" if timing_payload is None else timing_payload)
            + _integer(2, execution_status)
            + _integer(5, int(executed))
        )
    if timing_payload is not None:
        if not isinstance(timing_payload, bytes):
            raise ValueError("Unknown native TimeDatas")
        payload += b"\x5a" + _varint(len(timing_payload)) + timing_payload
    return payload


def null_listener_clone_payload(
    original, *, uid, base_uid, execution_status, caster_id, target_id
):
    """Qe.h/k eXE copy: preserve container/clocks, replace clone identity/status."""
    from .combat_effect_removal import _read_varint, _identity_fields

    identity = _identity_fields(original)
    if identity[1] != base_uid or identity[4] != 0:
        raise ValueError("Null listener clone requires its original zero-value payload")
    # Validate UID and execution status with the common native encoder.
    owned_effect_payload(
        uid=uid,
        base_uid=base_uid,
        generic_effect=identity[3],
        caster_id=caster_id,
        target_id=target_id,
        value=0,
        execution_status=execution_status,
    )

    def fields(data):
        offset = 0
        while offset < len(data):
            start = offset
            tag, offset = _read_varint(data, offset)
            field, wire = tag >> 3, tag & 7
            content = None
            if wire == 0:
                _, offset = _read_varint(data, offset)
            elif wire == 2:
                length, offset = _read_varint(data, offset)
                content = data[offset : offset + length]
                offset += length
            elif wire in (1, 5):
                offset += 8 if wire == 1 else 4
            else:
                raise ValueError("Unsupported native listener protobuf wire type")
            if not field or offset > len(data):
                raise ValueError("Invalid native listener protobuf")
            yield field, data[start:offset], content

    preserved, timing = [], None
    for field, encoded, content in fields(original):
        if field == 11:
            if timing is not None:
                raise ValueError("Duplicate native listener TimeDatas")
            timing = b"".join(
                raw for key, raw, _ in fields(content) if key not in (2, 5)
            )
        elif field not in (1, 2, 4, 6, 7):
            preserved.append(encoded)
    if timing is None:
        raise ValueError("Missing original native listener TimeDatas")
    timing += _integer(2, execution_status) + _integer(5, 1)
    return (
        _integer(1, uid)
        + _integer(2, base_uid)
        + _integer(4, 0)
        + _integer(6, caster_id)
        + _integer(7, target_id)
        + b"".join(preserved)
        + b"\x5a"
        + _varint(len(timing))
        + timing
    )


def owned_effect_application(
    fight_id,
    action_id,
    *,
    effect_class,
    target_id,
    uid,
    running_effect_payload,
    sequence=-1,
):
    """cvY13497 prefix; validation shared with cvZ13560 owned removal."""
    return running_effect_removal(
        fight_id,
        action_id,
        effect_class=effect_class,
        target_id=target_id,
        uid=uid,
        running_effect_payload=running_effect_payload,
        sequence=sequence,
        notify_unapplication=False,
    )[:-16]


def owned_effect_delivery(fight_id, action_id, *, native_opcode=13497, **arguments):
    """Native eXE requires cvX/aVo registration; eYg uses cvY/aTR.

    The false eIK byte retains the evaluated runner without executing gameplay
    again. UID, PL and TimeDatas bytes remain unchanged.
    """
    payload = owned_effect_application(fight_id, action_id, **arguments)
    if native_opcode == 12613:
        return 12613, payload[:12] + b"\x00" + payload[12:]
    if native_opcode != 13497:
        raise ValueError("Unsupported native owned delivery opcode")
    return 13497, payload


def evaluated_effect_delivery(fight_id, action_id, *, retained, **arguments):
    """Execute a decoded native mutation without recalculating its parameters.

    aVo/eIK=true applies an immediate runner directly. Its false branch retains
    a persistent runner on the actual native manager before c(); Qf ownership
    stays governed by the runner's own Ty/PK rather than a fabricated record.
    """
    from .combat_observation_delivery import evaluated_application_from_observation

    if type(retained) is not bool:
        raise ValueError("Explicit native application retention required")
    body = owned_effect_application(fight_id, action_id, **arguments)
    return 12613, evaluated_application_from_observation(body, execute=not retained)
