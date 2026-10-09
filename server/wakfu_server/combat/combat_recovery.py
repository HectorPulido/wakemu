"""Native coX13332/cvn12053 recovery from actual owned timeline snapshots."""
import struct


def timeline(fight, *, deadline_ms, bonus_counts=None):
    if fight.phase != "active" or fight.current is None:
        raise ValueError("Recovery requires an active fight")
    actors = list(fight.actors.values())
    from .combat_timeline_snapshot import counters

    progress = counters(fight)
    members = {int(identity) for identity in progress}
    if (
        len(actors) > 127
        or not fight.order
        or len(fight.order) > 127
        or set(fight.order) != members
        or any(
            identity not in fight.actors or fight.actors[identity].hp <= 0
            for identity in members
        )
    ):
        raise ValueError("Inconsistent live native timeline members")
    # PB114 creatures remain in the complete fight roster, but never Tc/SY.
    for actor in actors:
        if (
            actor.hp > 0
            and not getattr(actor, "pve_withdrawn", False)
            and actor.id not in members
        ):
            registration = getattr(fight, "native_summon_registrations", {}).get(
                actor.id
            )
            if registration is None or 114 not in registration["fight_properties"]:
                raise ValueError("Live actor lacks authoritative timeline membership")
    round_number = getattr(fight, "native_timeline_round", None)
    if (
        type(round_number) is not int
        or not -32768 <= round_number <= 32767
        or not 0 < fight.turn_id < 2**31
    ):
        raise ValueError("Invalid live native timeline counters")
    out = struct.pack(">hiBq", round_number, fight.turn_id, 1, deadline_ms)
    next_order = getattr(fight, "native_base_turn_order", None)
    next_order = fight.order if next_order is None else next_order
    if set(next_order) != members or len(next_order) > 127:
        raise ValueError("Inconsistent next-round native order")
    for identities in (fight.order, next_order):
        out += struct.pack(">b", len(identities)) + b"".join(
            struct.pack(">q", identity) for identity in identities
        )
    out += struct.pack(">b", len(progress)) + b"".join(
        struct.pack(">qh", int(identity), value) for identity, value in progress.items()
    )
    if (
        not 0 <= fight.turn_index < len(fight.order)
        or fight.order[fight.turn_index] != fight.current.id
    ):
        raise ValueError("Inconsistent current native timeline slot")
    out += struct.pack(">b", fight.turn_index)
    removed = getattr(fight, "native_timeline_removed", None)
    if not isinstance(removed, list) or len(removed) > 127:
        raise ValueError("Missing authoritative native removal statuses")
    out += struct.pack(">b", len(removed))
    for row in removed:
        if row["modifications"]:
            raise ValueError("Unsupported native pending removed-turn modifications")
        out += struct.pack(
            ">qhih", row["actor_id"], row["progress"], row["position"], 0
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
