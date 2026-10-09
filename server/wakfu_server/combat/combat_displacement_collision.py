"""Native eXD.fPh collision AP executions followed by explicit event204.

This component never interprets a blocked movement as a successful truncated
path. The caller must already have validated faz's geometry and fPa collision.
"""
from dataclasses import replace
from .combat_event_replay import NativeEventSource, NativeCloneAuthority


def collision_event_sources(
    invocation,
    *,
    uid,
    value,
    displaced_id,
    collider_id,
    collider_uid=None,
    suppresses_level_one,
    suppresses_all,
    suppressed
):
    """eXD.fPh + lambda a(BitSet,PV): 30caster/3target, repeated for collider.

    The second pair uses Qe.bbm().f(collider), hence a NEW running UID.
    Only caster channel30 uses that clone; collider channel3 receives the
    original source effect, with original UID and displaced target identity.
    Delivery channels30/3 are roles, not event IDs. No global channel is added:
    fPh calls PV.a directly rather than Qe.L lifecycle routing.
    """
    parent = (
        None
        if invocation.native_trigger_context is None
        else invocation.native_trigger_context["uid"]
    )
    base = NativeEventSource(
        uid,
        invocation.reference,
        value,
        invocation.caster_id,
        displaced_id,
        invocation.cell,
        (204,),
        3,
        displaced_id,
        parent,
        suppresses_level_one,
        suppresses_all,
        suppressed,
        True,
    )
    base.validate()
    sources = [replace(base, channel=30, manager_actor_id=invocation.caster_id), base]
    if collider_id is not None:
        if type(collider_id) is not int or collider_id == 0:
            raise ValueError("Invalid native actor collision identity")
        if (
            type(collider_uid) is not int
            or not 0 < collider_uid < (1 << 63)
            or collider_uid == uid
        ):
            raise ValueError("Missing fresh native Qe.bbm collision clone UID")
        other = replace(
            base, uid=collider_uid, target_id=collider_id, manager_actor_id=collider_id
        )
        sources.extend(
            (
                replace(other, channel=30, manager_actor_id=invocation.caster_id),
                replace(base, manager_actor_id=collider_id),
            )
        )
    return tuple(sources)


def apply_collision(
    *,
    invocation,
    uid,
    value,
    displaced_id,
    collider_id,
    loss_ap,
    ap_loss_executor,
    replay,
    clone_authority,
    allocate_clone_uid=None,
    suppresses_level_one,
    suppresses_all,
    suppressed
):
    """Native order: AP loss displaced, AP loss collider, then event204 pairs.

    Executors and replay must share the same private preview/transaction. The
    AP executor includes eVZ lifecycle and state5227, not only AP subtraction.
    """
    if type(loss_ap) is not bool:
        raise ValueError("Unknown native collision AP-loss policy")
    if not callable(replay) or not isinstance(clone_authority, NativeCloneAuthority):
        raise ValueError("Native collision requires event204 replay authority")
    if loss_ap and not callable(ap_loss_executor):
        raise ValueError("Native collision requires full eVZ AP-loss executor")
    if collider_id is not None and not callable(allocate_clone_uid):
        raise ValueError("Native collision requires Qe.bbm UID allocator")
    sources = collision_event_sources(
        invocation,
        uid=uid,
        value=value,
        displaced_id=displaced_id,
        collider_id=None,
        suppresses_level_one=suppresses_level_one,
        suppresses_all=suppresses_all,
        suppressed=suppressed,
    )
    if loss_ap:
        ap_loss_executor(invocation.caster_id, displaced_id)
        if collider_id is not None:
            ap_loss_executor(invocation.caster_id, collider_id)
    outcomes = [replay(source, authority=clone_authority) for source in sources]
    if collider_id is not None:
        # The native clone is constructed only after the displaced pair replay.
        all_sources = collision_event_sources(
            invocation,
            uid=uid,
            value=value,
            displaced_id=displaced_id,
            collider_id=collider_id,
            collider_uid=allocate_clone_uid(),
            suppresses_level_one=suppresses_level_one,
            suppresses_all=suppresses_all,
            suppressed=suppressed,
        )
        outcomes.extend(
            replay(source, authority=clone_authority) for source in all_sources[2:]
        )
    return tuple(outcomes)
