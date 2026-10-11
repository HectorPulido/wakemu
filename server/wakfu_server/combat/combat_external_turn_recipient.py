"""Explicit Wakemu caller policy for owned-turn recipients, preserving null Qe.

Native eZR.l(null) keeps the listener target. The server owns turn publication
and supplies its actual participant separately; this is a reconstruction policy,
not a fabricated source runner or a change to native null-source rebinding.
"""
from contextlib import contextmanager

_SCOPE = "_wakemu_owned_turn_recipient_scope"


@contextmanager
def owned_turn_recipient_scope(fight, context):
    from .combat_turn_events import validate_turn_boundary_context

    validate_turn_boundary_context(context, fight=fight)
    previous = getattr(fight, _SCOPE, None)
    if previous is not None:
        raise ValueError("Nested owned turn recipient publication")
    setattr(fight, _SCOPE, context)
    try:
        yield
    finally:
        delattr(fight, _SCOPE)


def external_turn_recipient(fight, source, *, target_code, original_target):
    from .combat_event_replay import NativeExternalEvent
    from .combat_turn_events import validate_turn_boundary_context

    if (
        not isinstance(source, NativeExternalEvent)
        or target_code != 5
        or source.turn_boundary_context is None
    ):
        return original_target
    context = source.turn_boundary_context
    validate_turn_boundary_context(context, fight=fight)
    if getattr(fight, _SCOPE, None) is not context:
        raise ValueError("Unattested owned turn recipient publication")
    if source.event_ids != (context["event_id"],):
        raise ValueError("Owned turn recipient event mismatch")
    actor = fight.actors.get(context["actor_id"])
    if actor is None or actor is not fight.current:
        raise ValueError("Owned turn recipient actor mismatch")
    return actor.id


def qualified_boundary_actor(fight, *, turn_context=None, movement_context=None):
    """Actual caller participant; this supplies no native triggering runner."""
    if turn_context is not None and movement_context is not None:
        raise ValueError("Ambiguous external participant boundary")
    if movement_context is not None:
        from .combat_external_movement_recipient import committed_movement_actor

        return committed_movement_actor(fight, movement_context)
    if turn_context is None:
        return None
    from .combat_turn_events import validate_turn_boundary_context

    validate_turn_boundary_context(turn_context, fight=fight)
    if getattr(fight, _SCOPE, None) is not turn_context:
        raise ValueError("Unattested owned turn recipient publication")
    actor = fight.actors.get(turn_context["actor_id"])
    if actor is None or actor is not fight.current:
        raise ValueError("Owned turn recipient actor mismatch")
    return actor


def external_movement_recipient(fight, source, *, target_code, original_target):
    from .combat_event_replay import NativeExternalEvent

    if (
        not isinstance(source, NativeExternalEvent)
        or target_code != 5
        or source.movement_boundary_context is None
    ):
        return original_target
    if source.event_ids != (1005,):
        raise ValueError("Committed movement recipient event mismatch")
    return qualified_boundary_actor(
        fight, movement_context=source.movement_boundary_context
    ).id
