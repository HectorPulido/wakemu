"""Native cpf13952 request and normal cvF12238 forfeit cleanup continuation.

The client proves the GUI/protocol path, not an official server HP penalty.
Local abandonment preserves authoritative damage already taken, grants no
rewards and releases the encounter. A sole controlled participant is required;
partially abandoning a shared multi-player fight is not implemented.
"""
import copy
import struct
from . import combat_health, combat_results, health
from .combat_lifecycle import outside_progression


def _participant(account_id, character, runtime):
    fight = runtime.fight
    actor = fight.actors.get(character["id"])
    controlled = [a for a in fight.actors.values() if a.controlled]
    if (
        actor is None
        or not actor.controlled
        or actor.owner_id != account_id
        or len(controlled) != 1
    ):
        raise ValueError("Unsupported or foreign abandon participant")
    return actor


def placement_runtime(fight, runtime):
    """Provide the missing message FSM for an owned pre-Ready cancellation.

    Ready initialization is transactional and may fail before a RuntimeMessages
    exists. Cancelling placement must not depend on successful initialization.
    Existing active runtimes retain their counters and pending continuations.
    """
    if runtime is not None:
        if runtime.fight is not fight:
            raise ValueError("Abandon runtime disagrees with authoritative fight")
        return runtime
    if fight is None or fight.phase != "placement":
        raise ValueError("Missing abandon message runtime outside placement")
    from .combat_runtime_messages import RuntimeMessages

    return RuntimeMessages(fight)


def prepare(store, account_id, generation, character, runtime, body):
    """Persist local abort HP, send cleanup and await native12925 callback."""
    if body != b"":
        raise ValueError("Invalid native abandon request")
    participant = _participant(account_id, character, runtime)
    owner = (account_id, character["id"])
    if getattr(runtime, "abandon_owner", None) == owner:
        saved = combat_health.persist(
            store, account_id, generation, character, runtime.fight, reason="abort"
        )["character"]
        return dict(character=saved, packets=[], applied=False)
    if runtime.fight.phase not in ("placement", "active"):
        raise ValueError("Fight cannot be abandoned in this phase")
    # Build without mutating the authoritative FSM before ownership/HP CAS.
    planned = copy.copy(runtime)
    planned.fight = copy.copy(runtime.fight)
    # huN=true removes a participant, then aUH returns early when its removal
    # leaves fewer than fUM teams. Normal end lists bypass that branch and
    # restore local input/frames; the authoritative FSM still records abort.
    winners = [
        a.id for a in runtime.fight.actors.values() if a.team != participant.team
    ]
    losers = [a.id for a in runtime.fight.actors.values() if a.team == participant.team]
    if not winners or max(len(winners), len(losers)) > 127:
        raise ValueError("Unsupported abandon team layout")
    payload = planned._prefix() + b"\x00"
    # ckc routes eIl (second list) through buH.W into jqB; aUH
    # derives its loss presentation flag from !jqB.contains(own actor).
    # The first list is therefore losers, the second winners.
    for identities in (losers, winners, []):
        payload += struct.pack(">b", len(identities)) + b"".join(
            struct.pack(">q", identity) for identity in identities
        )
    packets = [(12238, payload), planned._flush()]
    exit_health = combat_health.persist(
        store, account_id, generation, character, runtime.fight, reason="abort"
    )
    runtime.fight.phase = "finished"
    runtime.fight.winner = None
    runtime.awaiting_ack = None
    runtime.pending = []
    runtime.action_id = planned.action_id
    runtime.abandon_owner = owner
    runtime.abandon_returned = False
    return dict(character=exit_health["character"], packets=packets, applied=True)


def return_to_world(
    store, account_id, generation, character, runtime, body, *, wp, ap=6, mp=3
):
    """Apply only the matching12925 after native aUH has cleaned the fight UI."""
    _participant(account_id, character, runtime)
    if (
        getattr(runtime, "abandon_owner", None) != (account_id, character["id"])
        or runtime.fight.phase != "finished"
        or runtime.fight.winner is not None
    ):
        raise ValueError("No owned abandon continuation")
    # huO is a client presentation result, not authority to reverse the
    # already persisted abort. Accept either native boolean after validating
    # the fight ID and owned abort; this also recovers old reversed-list ends.
    combat_results.continuation(runtime.fight.id, body)
    if runtime.abandon_returned:
        saved = combat_health.persist(
            store, account_id, generation, character, runtime.fight, reason="abort"
        )["character"]
        return dict(character=saved, packets=[], applied=False)
    result = combat_health.persist(
        store, account_id, generation, character, runtime.fight, reason="abort"
    )
    saved = result["character"]
    packets = combat_results.outside_fight_updates(runtime.fight)
    packets.extend(
        [
            outside_progression(saved, wp=wp, ap=ap, mp=mp),
            (
                12436,
                health.packet(saved["id"], saved["hp"], 1 if saved["hp"] > 0 else 0),
            ),
        ]
    )
    runtime.abandon_returned = True
    return dict(character=saved, packets=packets, applied=True)
