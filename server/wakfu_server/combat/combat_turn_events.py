"""Separate native turn phases, with explicit emulated-server delivery policy.

Installed effect descriptions197715/339741 identify1001 as start;343079/339766
identify1002 as end. No client server-producer callsite is claimed. Null source,
channels and the timing relative to expiration are server policy; Qf retains
its native priority, masks and criteria. Each owned boundary is delivered once.
"""
from .combat_event_replay import NativeExternalEvent


TURN_BOUNDARY_POLICY = "wakemu.owned-turn-boundary-facts-v1"


def validate_turn_boundary_context(context, *, fight=None):
    """Validate owned server facts while preserving the native null Qe source."""
    events = {"start": 1001, "end": 1002, "regeneration": 1037}
    if (
        not isinstance(context, dict)
        or set(context) != {"policy", "actor_id", "turn_id", "phase", "event_id"}
        or context.get("policy") != TURN_BOUNDARY_POLICY
        or type(context.get("actor_id")) is not int
        or context["actor_id"] == 0
        or type(context.get("turn_id")) is not int
        or type(context.get("event_id")) is not int
        or type(context.get("phase")) is not str
        or context["phase"] not in events
        or events[context["phase"]] != context["event_id"]
    ):
        raise ValueError("Invalid owned turn boundary facts")
    if fight is not None and (
        fight.phase != "active"
        or fight.current is None
        or fight.current.id != context["actor_id"]
        or fight.turn_id != context["turn_id"]
    ):
        raise ValueError("Owned turn boundary facts differ from active turn")
    return context


def _deliver(dispatcher, *, actor_id, phase, event_id, suppression_phase=None):
    fight = dispatcher.native_retention.fight
    actor = fight.current
    if fight.phase != "active" or actor is None or actor.id != actor_id:
        raise ValueError("Turn boundary requires the actual active actor")
    if not fight.native_start_event_delivered:
        raise ValueError("Native participant initialization/start is incomplete")
    key = f"{fight.turn_id}:{actor_id}:{phase}"
    deliveries = getattr(fight, "native_turn_event_deliveries", {})
    if key in deliveries:
        raise ValueError("Owned turn boundary already delivered")
    context = validate_turn_boundary_context(
        dict(
            policy=TURN_BOUNDARY_POLICY,
            actor_id=actor_id,
            turn_id=fight.turn_id,
            phase=phase,
            event_id=event_id,
        ),
        fight=fight,
    )
    authority = dispatcher.native_clone_authority
    outcomes = []
    from .combat_turn_suppression import turn_phase_suppressed

    suppressed = turn_phase_suppressed(actor, suppression_phase or phase)
    # Local/reversed subscribers belong to the actor at this boundary. Global
    # subscribers receive the same boundary in each participant's manager.
    recipients = [(actor_id, 6), (actor_id, 60)]
    from .combat_native_actor_lookup import native_actor_population

    # Native global delivery captures the registered IN_PLAY/OFF_PLAY PV
    # population. Retained OUT_OF_PLAY corpses remain in fight.actors for
    # history, but their managers cannot receive new global turn reactions.
    recipients += [(candidate.id, 61) for candidate in native_actor_population(fight)]
    if suppressed:
        recipients = []  # fbX.A/z returns before native QP/QO phase delivery.
    from .combat_external_turn_recipient import owned_turn_recipient_scope

    with owned_turn_recipient_scope(fight, context):
        for identity, channel in recipients:
            outcomes.extend(
                dispatcher.replay_event(
                    NativeExternalEvent(
                        identity, (event_id,), channel, turn_boundary_context=context
                    ),
                    authority=authority,
                )
            )
    # Caller operates on an unpublished preview: exception discards all effects.
    deliveries = dict(deliveries)
    deliveries[key] = {
        "actor_id": actor_id,
        "turn_id": fight.turn_id,
        "event_id": event_id,
        "phase": phase,
        "suppressed": suppressed,
    }
    fight.native_turn_event_deliveries = deliveries
    return tuple(outcomes)


def deliver_turn_start(dispatcher, *, actor_id):
    return _deliver(dispatcher, actor_id=actor_id, phase="start", event_id=1001)


def deliver_turn_end(dispatcher, *, actor_id):
    return _deliver(dispatcher, actor_id=actor_id, phase="end", event_id=1002)


def deliver_turn_regeneration(dispatcher, *, actor_id):
    """Replay native1037 regeneration at the owned end boundary.

    Installed343565 and6935 descriptions place natural regeneration at end
    of turn;343570 subscribes1037 and its child343571 gains current WP.
    Delivery after1002 and before expiry is explicit server ordering policy;
    no original client producer or direct resource refill is asserted.
    """
    return _deliver(
        dispatcher,
        actor_id=actor_id,
        phase="regeneration",
        event_id=1037,
        suppression_phase="end",
    )
