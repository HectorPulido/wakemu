"""Separate native turn phases, with explicit emulated-server delivery policy.

Installed effect descriptions197715/339741 identify1001 as start;343079/339766
identify1002 as end. No client server-producer callsite is claimed. Null source,
channels and the timing relative to expiration are server policy; Qf retains
its native priority, masks and criteria. Each owned boundary is delivered once.
"""
from .combat_event_replay import NativeExternalEvent


def _deliver(dispatcher, *, actor_id, phase, event_id):
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
    authority = dispatcher.native_clone_authority
    outcomes = []
    # Local/reversed subscribers belong to the actor at this boundary. Global
    # subscribers receive the same boundary in each participant's manager.
    recipients = [(actor_id, 6), (actor_id, 60)]
    recipients += [(identity, 61) for identity in tuple(fight.actors)]
    for identity, channel in recipients:
        outcomes.extend(
            dispatcher.replay_event(
                NativeExternalEvent(identity, (event_id,), channel), authority=authority
            )
        )
    # Caller operates on an unpublished preview: exception discards all effects.
    deliveries = dict(deliveries)
    deliveries[key] = {
        "actor_id": actor_id,
        "turn_id": fight.turn_id,
        "event_id": event_id,
        "phase": phase,
    }
    fight.native_turn_event_deliveries = deliveries
    return tuple(outcomes)


def deliver_turn_start(dispatcher, *, actor_id):
    return _deliver(dispatcher, actor_id=actor_id, phase="start", event_id=1001)


def deliver_turn_end(dispatcher, *, actor_id):
    return _deliver(dispatcher, actor_id=actor_id, phase="end", event_id=1002)
