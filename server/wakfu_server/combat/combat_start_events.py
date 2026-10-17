"""Server inferred fight-start contract, preserving native null-source replay.

1003's start-combat meaning is supported by installed localized definitions.
1028 installs opening mechanics (e.g. Steamer343565 converts PW to SP
and grants its secondary spells). The installed description explicitly places
that group at combat start. Native ordinary NPC states also subscribe1028
(e.g. Ogrest4979/5022). Delivery before1003 is server policy: every installed
participant receives its own opening event before general start reactions.
The server-only producer boundary (all participants installed, at the first
turn boundary) is an explicit implementation inference; no client callsite proves it.
The server establishes the validated first native timeline round before replay
so first-round criteria observe that boundary even before wire13477 delivery.
"""
from .combat_event_replay import NativeExternalEvent


def deliver_fight_start(dispatcher, *, initialized_actor_ids):
    retention = dispatcher.native_retention
    fight = retention.fight
    if fight.native_start_event_delivered:
        raise ValueError("Fight-start event already delivered")
    identities = tuple(initialized_actor_ids)
    if len(identities) != len(set(identities)) or set(identities) != set(fight.actors):
        raise ValueError("All native participant roots must be installed before start")
    if (
        fight.phase != "active"
        or fight.turn_id != 1
        or any(
            a.turn_count != (1 if a is fight.current else 0)
            for a in fight.actors.values()
        )
    ):
        raise ValueError(
            "Fight-start event requires active fight at first-turn boundary"
        )
    installed = getattr(fight, "native_class_initializations", {})
    if any(a.controlled and a.id not in installed for a in fight.actors.values()):
        raise ValueError("Controlled native class roots are not initialized")
    # Explicit Wakemu startup policy: the private preview is already in the
    # first native SU cycle, while wire13477 is emitted later by RuntimeMessages.
    # Publish that existing cycle to criteria before the once-only start replay.
    native_round = getattr(fight, "native_timeline_round", None)
    table_turn = getattr(fight, "native_table_turn", None)
    if (
        type(native_round) is not int
        or native_round != 1
        or type(table_turn) is not int
        or table_turn not in (0, 1)
    ):
        raise ValueError("Fight-start event requires the native first-round counter")
    authority = dispatcher.native_clone_authority
    fight.native_table_turn = native_round
    # Caller supplies the private transaction preview; any exception discards it.
    outcomes = []
    # Opening listeners belong to native PC and NPC initial-state managers.
    # Each receives its own null-source event; this creates no class receipt.
    for identity in identities:
        for channel in (6, 60, 61):
            outcomes.extend(
                dispatcher.replay_event(
                    NativeExternalEvent(identity, (1028,), channel), authority=authority
                )
            )
    for identity in identities:
        for channel in (6, 60, 61):
            outcomes.extend(
                dispatcher.replay_event(
                    NativeExternalEvent(identity, (1003,), channel), authority=authority
                )
            )
    fight.native_start_event_delivered = True
    return tuple(outcomes)
