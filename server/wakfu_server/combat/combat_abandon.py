"""Native cpf13952 request and normal cvF12238 forfeit cleanup continuation.

The client proves the GUI/protocol path, not an official server HP penalty.
Local abandonment preserves authoritative damage already taken, grants no
rewards and releases the encounter. A sole remaining controlled participant is
required; individual shared PvE exits use combat_pve_withdraw instead.
"""
import copy
import struct
from . import combat_health, combat_results, health
from .combat_lifecycle import outside_progression


def _participant(account_id, character, runtime):
    fight = runtime.fight
    from .combat_terminal_metadata import registered_summon_actor_ids

    summon_ids = registered_summon_actor_ids(fight)
    if any(
        member.id not in summon_ids
        and (
            getattr(member, "native_summon_source", None) is not None
            or getattr(member, "is_summon", False) is True
        )
        for member in fight.actors.values()
    ):
        raise ValueError("Abandon roster contains an unregistered native summon")
    actor = fight.actors.get(character["id"])
    controlled = [
        a
        for a in fight.actors.values()
        if a.controlled
        and a.id not in summon_ids
        and not getattr(a, "pve_withdrawn", False)
    ]
    if (
        actor is None
        or actor.id in summon_ids
        or not actor.controlled
        or actor.owner_id != account_id
        or getattr(actor, "pve_withdrawn", False)
        or any(member.owner_id != account_id for member in controlled)
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


def _terminal_packets(planned, losing_team):
    # huN=true removes a participant, then aUH returns early when its removal
    # leaves fewer than fUM teams. Normal end lists bypass that branch and
    # restore local input/frames; the authoritative FSM still records abort.
    winners = [a.id for a in planned.fight.actors.values() if a.team != losing_team]
    losers = [a.id for a in planned.fight.actors.values() if a.team == losing_team]
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
    return [(12238, payload), planned._flush()]


def committed_abandon_team(runtime):
    """Return the team of an owned continuation installed after durable abort.

    prepare installs abandon_owner only after its status/health transaction
    commits. A pending victory or an absent continuation is not this boundary.
    """
    owner = getattr(runtime, "abandon_owner", None)
    if owner is None:
        return None
    fight = getattr(runtime, "fight", None)
    if (
        not isinstance(owner, tuple)
        or len(owner) != 2
        or any(type(identity) is not int or identity <= 0 for identity in owner)
        or fight is None
        or fight.phase != "finished"
        or fight.winner is not None
    ):
        raise ValueError("Invalid committed abandonment continuation")
    actor = fight.actors.get(owner[1])
    if (
        actor is None
        or not actor.controlled
        or actor.owner_id != owner[0]
        or getattr(actor, "pve_withdrawn", False)
        or actor.team not in (0, 1)
    ):
        raise ValueError("Committed abandonment participant is stale")
    return actor.team


def aborted_terminal_packets(fight, runtime=None, *, losing_team):
    """Normal spectator cleanup for an already committed abort, no winner.

    Reuse the abandonment codec on a detached counter snapshot. This function
    neither persists health nor changes the authoritative outcome or runtime.
    """
    if (
        fight.phase != "finished"
        or fight.winner is not None
        or losing_team not in (0, 1)
    ):
        raise ValueError("Spectator abort requires a committed aborted fight")
    if runtime is None:
        from .combat_runtime_messages import RuntimeMessages

        runtime = RuntimeMessages(fight)
    if runtime.fight is not fight:
        raise ValueError("Aborted spectator runtime is stale")
    planned = copy.copy(runtime)
    planned.fight = copy.copy(fight)
    return _terminal_packets(planned, losing_team)


def prepare(store, account_id, generation, character, runtime, body):
    """Persist local abort HP, send cleanup and await native12925 callback."""
    if body != b"":
        raise ValueError("Invalid native abandon request")
    participant = _participant(account_id, character, runtime)
    owner = (account_id, character["id"])
    if getattr(runtime, "abandon_owner", None) == owner:
        saved = combat_health.persist_owned(
            store, account_id, generation, character, runtime.fight, reason="abort"
        )["character"]
        return dict(character=saved, packets=[], applied=False)
    if runtime.fight.phase not in ("placement", "active"):
        raise ValueError("Fight cannot be abandoned in this phase")
    # Build without mutating the authoritative FSM before ownership/HP CAS.
    planned = copy.copy(runtime)
    planned.fight = copy.copy(runtime.fight)
    packets = _terminal_packets(planned, participant.team)
    # The durable outcome must not depend on the subsequent checkpoint or
    # client callback. Commit the abort and its health receipt together.
    with store.connection() as db:
        # Keep the same fight-before-session/character ordering used by
        # persist_aborted_fight, settlement, and join. Otherwise two callbacks
        # can deadlock when this path owns the character row and another path
        # already owns the fight row while waiting for that character.
        if (
            db.execute(
                "SELECT id FROM combat_fights WHERE id=%s FOR UPDATE",
                (runtime.fight.id,),
            ).fetchone()
            is None
        ):
            raise ValueError("Fight cannot be durably abandoned")
        exit_health = combat_health.persist_owned(
            store,
            account_id,
            generation,
            character,
            runtime.fight,
            reason="abort",
            db=db,
        )
        cursor = db.execute(
            "UPDATE combat_fights SET status='aborted' WHERE id=%s "
            "AND status IN ('placement','active','aborted')",
            (runtime.fight.id,),
        )
        if cursor.rowcount != 1:
            raise ValueError("Fight cannot be durably abandoned")
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
    result = combat_health.persist_owned(
        store, account_id, generation, character, runtime.fight, reason="abort"
    )
    if runtime.abandon_returned:
        return dict(character=result["character"], packets=[], applied=False)
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
