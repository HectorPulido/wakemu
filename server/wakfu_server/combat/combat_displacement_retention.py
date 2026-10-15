"""Owned eXK/eXJ retained runners; removal never reverses their movement."""
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_delivery
from .combat_effects import _varint


FAMILIES = (300, 301)


def retained_displacement_context(handler, effect, invocation, timing):
    if not timing["retained"]:
        return None
    if effect["effect_class"] not in FAMILIES or not callable(handler.context):
        raise ValueError("Missing retained native displacement execution context")
    from .combat_carry_handler import NativeCarryHandler

    NativeCarryHandler.require_execution_context(invocation)
    ctx = handler.context(effect, invocation)
    if (
        not isinstance(ctx, StatExecutionContext)
        or ctx.source_guards_verified is not True
        or type(ctx.executable) is not bool
        or type(ctx.retained) is not bool
    ):
        raise ValueError("Unverified retained native displacement execution context")
    return ctx


def retain_displacement(
    handler, effect, invocation, ctx, *, uid, source, target, value, additional
):
    """Store the same evaluated Qe payload used by cvX and later cvZ removal."""
    from .combat_displacement import position_payload

    if effect["effect_class"] not in FAMILIES or ctx.retained is not True:
        raise ValueError("Wrong retained native displacement runner")
    if not isinstance(invocation.native_context_hex, str):
        raise ValueError("Missing retained native displacement eVt context")
    payload = owned_effect_payload(
        uid=uid,
        base_uid=invocation.base_uid,
        generic_effect=invocation.reference,
        caster_id=source.id,
        target_id=target.id,
        value=value,
        timing_payload=ctx.timing_payload,
        execution_status=-1,
        executed=True,
    )
    for field, data in (
        (5, position_payload(invocation.cell)),
        (8, additional),
        (13, bytes.fromhex(invocation.native_context_hex)),
    ):
        payload += _varint(field << 3 | 2) + _varint(len(data)) + data
    if uid in handler.fight.owned_stat_effects:
        raise ValueError("Duplicate retained displacement UID")
    handler.fight.owned_stat_effects[uid] = dict(
        uid=uid,
        effect_class=effect["effect_class"],
        family="eXD",
        target_id=target.id,
        caster_id=source.id,
        stat_id=None,
        actual=value,
        payload=payload.hex(),
        state_uid=invocation.state_uid,
        timer=None if ctx.timer is None else dict(vars(ctx.timer)),
    )
    return owned_effect_delivery(
        handler.fight.id,
        handler.action_id,
        native_opcode=12613,
        effect_class=effect["effect_class"],
        target_id=target.id,
        uid=uid,
        running_effect_payload=payload,
    )


def remove_retained_displacement(handler, uid):
    # Neither eXK/eXJ nor eXD/eZR overrides Qe.bbR. Unapplication removes
    # ownership and delivers the original path payload; positions stay put.
    from .combat_force_characteristic import remove_forced_characteristic

    return remove_forced_characteristic(handler, uid)
