"""Exact native Qe.k -> j -> bbL lifetime for a subscribed eXc clone.

Qe.j marks only the newly allocated clone bfM=true; inherited eZR.Ty then
returns false before consulting definition duration. The original listener
keeps its own Qf registration and execution count.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


_current = ContextVar("native_kill_clone_lifetime", default=None)


@dataclass(frozen=True)
class KillCloneLifetime:
    fight: object
    uid: int
    parent_uid: int
    reference: int
    level: int
    caster_id: int
    target_id: int | None


def qualify(fight, effect, invocation, clone_uid):
    """Require the original subscribed eXc before accepting Qe.k's clone UID."""
    if (
        effect.get("effect_class") != 28
        or type(clone_uid) is not int
        or not 0 < clone_uid < (1 << 63)
        or invocation.native_running_uid is not None
        or type(invocation.base_uid) is not int
        or invocation.base_uid <= 0
        or clone_uid == invocation.base_uid
        or clone_uid in getattr(fight, "native_retained_records", {})
    ):
        raise ValueError("Missing native subscribed eXc clone identity")
    masks = effect.get("target_masks")
    if (
        not isinstance(masks, (list, tuple))
        or len(masks) != 7
        or not any(masks[index] for index in (0, 1, 3, 4, 5))
    ):
        raise ValueError("Native eXc clone lacks its subscribed definition masks")
    listener = getattr(fight, "native_owned_group_effects", {}).get(invocation.base_uid)
    original = None if listener is None else listener.get("invocation")
    if (
        listener is None
        or listener.get("effect_class") != 28
        or not isinstance(original, dict)
        or original.get("reference") != invocation.reference
        or original.get("level") != invocation.level
        or listener.get("state_uid") != invocation.state_uid
        or listener.get("native_subscription_masks") != masks
    ):
        raise ValueError("Missing original subscribed eXc listener")
    return KillCloneLifetime(
        fight,
        clone_uid,
        invocation.base_uid,
        invocation.reference,
        invocation.level,
        invocation.caster_id,
        invocation.target_id,
    )


def _matches(proof, fight, effect, invocation):
    return (
        type(proof) is KillCloneLifetime
        and proof.fight is fight
        and effect.get("effect_class") == 28
        and (
            invocation.native_running_uid,
            invocation.base_uid,
            invocation.reference,
            invocation.level,
            invocation.caster_id,
            invocation.target_id,
        )
        == (
            proof.uid,
            proof.parent_uid,
            proof.reference,
            proof.level,
            proof.caster_id,
            proof.target_id,
        )
    )


@contextmanager
def timing_scope(proof, fight, effect, invocation):
    if proof is None:
        yield
        return
    if not _matches(proof, fight, effect, invocation):
        raise ValueError("Native eXc clone lifetime escaped its allocated identity")
    token = _current.set(proof)
    try:
        yield
    finally:
        _current.reset(token)


def unretained(fight, effect, invocation):
    return _matches(_current.get(), fight, effect, invocation)
