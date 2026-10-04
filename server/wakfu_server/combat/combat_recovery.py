"""Native coX13332/cvn12053 recovery for the own fixed-roster PVE policy.

No summons, timeline insertion/delay, resurrection or bonus offers are inferred.
"""
import struct
from .combat_turns import initial_order


def timeline(fight, *, deadline_ms, bonus_counts=None):
    if fight.phase != "active" or fight.current is None:
        raise ValueError("Recovery requires an active fight")
    actors = list(fight.actors.values())
    alive = [a.id for a in actors if a.hp > 0]
    if len(actors) > 127 or set(alive) != set(fight.order):
        raise ValueError("Inconsistent live timeline roster")
    if not 0 < fight.turn_id < 2**31 or not 0 < fight.current.turn_count < 2**15:
        raise ValueError("Invalid live timeline counters")
    # Native SU: round, global started-turn count, ON_FIGHTER_TURN, deadline.
    out = struct.pack(">hiBq", fight.current.turn_count, fight.turn_id, 1, deadline_ms)
    # SX first array is the current-round order consumed by Tc.bil(); the
    # second is next-round order. Fixed local initiative uses the same order.
    for identities in (fight.order, fight.order):
        out += struct.pack(">b", len(identities)) + b"".join(
            struct.pack(">q", i) for i in identities
        )
    # SY.brM is insertion-round metadata, NOT actor's turn counter. All local
    # participants were inserted before placement; no timeline reinsertion exists.
    out += struct.pack(">b", len(alive)) + b"".join(
        struct.pack(">qh", i, 0) for i in alive
    )
    out += struct.pack(">b", fight.order.index(fight.current.id))
    original = initial_order(
        fight.id,
        [
            dict(
                id=a.id,
                team=a.team,
                initiative=a.initiative,
                effective_level=a.effective_level,
            )
            for a in actors
        ],
    )
    removed = []
    current = None
    for event in fight.events:
        if event["kind"] == "turn_started":
            current = event["actor_id"]
        if event["kind"] == "death":
            identity = event["actor_id"]
            if identity not in original:
                raise ValueError("Unsupported repeated timeline death")
            removed.append(
                (identity, 1 if identity == current else 0, original.index(identity))
            )
            original.remove(identity)
    if {r[0] for r in removed} != {a.id for a in actors if a.hp == 0}:
        raise ValueError("Missing authoritative death history")
    # fem.sbE removed fighter statuses: qID + feu(short insertion-round,
    # i32 former timeline position, i16 pending modifications count0).
    out += struct.pack(">b", len(removed))
    out += b"".join(
        struct.pack(">qhih", identity, round_number, index, 0)
        for identity, round_number, index in removed
    )
    # feN.rJ is bonus-point state. Native ac(-1) leaves its initial zero intact;
    # it must not be populated with Actor.turn_count.
    bonus_counts = {} if bonus_counts is None else bonus_counts
    out += struct.pack(">b", len(actors)) + b"".join(
        struct.pack(">qi", a.id, bonus_counts.get(a.id, 0)) for a in actors
    )
    return out


def recovery_packet(fight, body, *, deadline_ms, bonus_counts=None):
    if len(body) != 4 or struct.unpack(">i", body)[0] != fight.id:
        raise ValueError("Recovery request belongs to another fight")
    state = timeline(fight, deadline_ms=deadline_ms, bonus_counts=bonus_counts)
    # fg/fh field envelope: count1,(index0,absolute offset6), data marker0,
    # followed by fcc i16length+SU. cvn carries the complete fg envelope.
    envelope = struct.pack(">BBiBh", 1, 0, 6, 0, len(state)) + state
    if len(envelope) >= 32768:
        raise ValueError("Recovery state exceeds native short length")
    return 12053, struct.pack(">ih", fight.id, len(envelope)) + envelope
