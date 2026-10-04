"""Server inferred fight-start contract, preserving native null-source replay.

1003's start-combat meaning is supported by installed localized definitions.
The server-only producer boundary (all participants installed, before first
turn) is an explicit implementation inference; no client callsite proves it.
"""
from .combat_event_replay import NativeExternalEvent


def deliver_fight_start(dispatcher, *, initialized_actor_ids):
    retention = dispatcher.native_retention
    fight = retention.fight
    if fight.native_start_event_delivered:
        raise ValueError("Fight-start event already delivered")
    identities = tuple(initialized_actor_ids)
    if (len(identities) != len(set(identities))
            or set(identities) != set(fight.actors)):
        raise ValueError("All native participant roots must be installed before start")
    if (fight.phase != "active" or fight.turn_id != 1
            or any(a.turn_count != (1 if a is fight.current else 0)
                   for a in fight.actors.values())):
        raise ValueError("Fight-start event requires active fight at first-turn boundary")
    authority = dispatcher.native_clone_authority
    # Caller supplies the private transaction preview; any exception discards it.
    outcomes = []
    for identity in identities:
        outcomes.extend(dispatcher.replay_event(
            NativeExternalEvent(identity, (1003,), 6), authority=authority))
    fight.native_start_event_delivered = True
    return tuple(outcomes)
