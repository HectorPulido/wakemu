"""Owned turn delivery planning, separate from retained callback execution."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TurnBoundaryPlan:
    actor_id: int
    turn_id: int
    phase: str
    event_id: int
    suppressed: bool
    recipients: tuple[tuple[int, int], ...]


def prepare_turn_delivery(fight, *, actor_id, phase, event_id, suppression_phase=None):
    """Freeze native recipient order before any synchronous reaction executes.

    OFF_PLAY managers receive global events; OUT_OF_PLAY history does not.
    Suppression does not erase the once-only boundary marker. Eligibility of
    individual retained effects remains the authority of their native replay.
    """
    from .combat_turn_events import validate_turn_boundary_context, TURN_BOUNDARY_POLICY
    from .combat_turn_suppression import turn_phase_suppressed
    from .combat_native_actor_lookup import native_actor_population

    actor = fight.current
    if fight.phase != "active" or actor is None or actor.id != actor_id:
        raise ValueError("Turn boundary requires the actual active actor")
    if not fight.native_start_event_delivered:
        raise ValueError("Native participant initialization/start is incomplete")
    key = f"{fight.turn_id}:{actor_id}:{phase}"
    if key in getattr(fight, "native_turn_event_deliveries", {}):
        raise ValueError("Owned turn boundary already delivered")
    validate_turn_boundary_context(
        dict(
            policy=TURN_BOUNDARY_POLICY,
            actor_id=actor_id,
            turn_id=fight.turn_id,
            phase=phase,
            event_id=event_id,
        ),
        fight=fight,
    )
    suppressed = turn_phase_suppressed(actor, suppression_phase or phase)
    recipients = ((actor_id, 6), (actor_id, 60)) + tuple(
        (candidate.id, 61) for candidate in native_actor_population(fight)
    )
    return TurnBoundaryPlan(
        actor_id,
        fight.turn_id,
        phase,
        event_id,
        suppressed,
        () if suppressed else recipients,
    )


def execute_turn_delivery(dispatcher, plan):
    """Replay one prepared boundary; publication remains the caller's duty."""
    from .combat_event_replay import NativeExternalEvent
    from .combat_turn_events import TURN_BOUNDARY_POLICY, validate_turn_boundary_context
    from .combat_external_turn_recipient import owned_turn_recipient_scope
    from .combat_external_event_removal import (
        has_removal_subscription,
        removal_recipients,
    )

    fight = dispatcher.native_retention.fight
    deliveries = getattr(fight, "native_turn_event_deliveries", {})
    context = dict(
        policy=TURN_BOUNDARY_POLICY,
        actor_id=plan.actor_id,
        turn_id=plan.turn_id,
        phase=plan.phase,
        event_id=plan.event_id,
    )
    validate_turn_boundary_context(context, fight=fight)
    if f"{plan.turn_id}:{plan.actor_id}:{plan.phase}" in deliveries:
        raise ValueError("Owned turn boundary already delivered")
    outcomes = []
    authority = dispatcher.native_clone_authority
    with owned_turn_recipient_scope(fight, context):
        for identity, channel in plan.recipients:
            outcomes.extend(
                dispatcher.replay_event(
                    NativeExternalEvent(
                        identity,
                        (plan.event_id,),
                        channel,
                        turn_boundary_context=context,
                    ),
                    authority=authority,
                )
            )
        # Start/regeneration close the corresponding turn-scoped listeners.
        # Keep the original frozen manager order and the same owned boundary
        # facts; a null-source L6 notification alone cannot select mask2.
        if plan.event_id in (1001, 1037) and has_removal_subscription(
            dispatcher, plan.event_id
        ):
            for identity, channel in removal_recipients(plan.recipients):
                outcomes.extend(
                    dispatcher.replay_event(
                        NativeExternalEvent(
                            identity,
                            (plan.event_id,),
                            channel,
                            turn_boundary_context=context,
                        ),
                        authority=authority,
                    )
                )
    deliveries = dict(deliveries)
    deliveries[f"{plan.turn_id}:{plan.actor_id}:{plan.phase}"] = dict(
        actor_id=plan.actor_id,
        turn_id=fight.turn_id,
        event_id=plan.event_id,
        phase=plan.phase,
        suppressed=plan.suppressed,
    )
    fight.native_turn_event_deliveries = deliveries
    return tuple(outcomes)
