"""Native coX13332/cvn12053 recovery from actual owned timeline snapshots."""
import struct


def timeline(
    fight, *, deadline_ms, bonus_counts=None, excluded_actor_ids=(), new_turn=False
):
    if type(new_turn) is not bool:
        raise ValueError("Invalid native recovery turn phase")
    if fight.phase != "active" or fight.current is None:
        raise ValueError("Recovery requires an active fight")
    if not isinstance(excluded_actor_ids, (tuple, list, set, frozenset)):
        raise ValueError("Invalid initial recovery actor projection")
    if any(type(identity) is not int for identity in excluded_actor_ids):
        raise ValueError("Invalid initial recovery actor projection")
    if len(excluded_actor_ids) != len(set(excluded_actor_ids)):
        raise ValueError("Invalid initial recovery actor projection")
    excluded = set(excluded_actor_ids)
    actors = list(fight.actors.values())
    if excluded:
        registrations = getattr(fight, "native_summon_registrations", {})
        deliveries = getattr(fight, "native_summon_creation_deliveries", {})
        order_ids = set(fight.order)
        progress_ids = set(getattr(fight, "native_timeline_member_counters", {}))
        progress_ids = {
            int(identity)
            for identity in progress_ids
            if str(identity).lstrip("-").isdigit()
        }
        for identity in excluded:
            actor = fight.actors.get(identity)
            registration = registrations.get(identity)
            delivery = deliveries.get(identity)
            properties = (
                registration.get("fight_properties")
                if isinstance(registration, dict)
                else None
            )
            is_timeline_member = (
                isinstance(properties, (tuple, list, set, frozenset))
                and 114 not in properties
            )
            try:
                birth_payload = bytes.fromhex(delivery.get("payload_hex", ""))
            except (AttributeError, TypeError, ValueError):
                birth_payload = b""
            if (
                actor is None
                or identity == fight.current.id
                or not isinstance(registration, dict)
                or registration.get("actor_id") != identity
                or not isinstance(properties, (tuple, list, set, frozenset))
                or not isinstance(delivery, dict)
                or delivery.get("opcode") != 12613
                or not birth_payload
                or not getattr(actor, "native_summon_source", None)
                or (
                    is_timeline_member
                    and (identity not in order_ids or identity not in progress_ids)
                )
                or (
                    not is_timeline_member
                    and (identity in order_ids or identity in progress_ids)
                )
            ):
                raise ValueError("Unverified initial summon recovery exclusion")
        actors = [actor for actor in actors if actor.id not in excluded]
    from .combat_timeline_snapshot import counters

    progress = {
        identity: value
        for identity, value in counters(fight).items()
        if int(identity) not in excluded
    }
    members = {int(identity) for identity in progress}
    order = [identity for identity in fight.order if identity not in excluded]
    if (
        len(actors) > 127
        or not order
        or len(order) > 127
        or set(order) != members
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
            and 114 not in getattr(actor, "native_fight_properties", ())
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
    # SU.eE enters ON_FIGHTER_TURN from BEGINNING_FIGHTER_TURN and
    # increments its global turn once. A restored ongoing turn must not replay
    # that boundary. Tc/SY progress belongs to end-turn and stays unchanged.
    out = struct.pack(
        ">hiBq",
        round_number,
        fight.turn_id - int(new_turn),
        4 if new_turn else 1,
        deadline_ms,
    )
    next_order = getattr(fight, "native_base_turn_order", None)
    next_order = (
        order
        if next_order is None
        else [identity for identity in next_order if identity not in excluded]
    )
    if set(next_order) != members or len(next_order) > 127:
        raise ValueError("Inconsistent next-round native order")
    for identities in (order, next_order):
        out += struct.pack(">b", len(identities)) + b"".join(
            struct.pack(">q", identity) for identity in identities
        )
    out += struct.pack(">b", len(progress)) + b"".join(
        struct.pack(">qh", int(identity), value) for identity, value in progress.items()
    )
    if (
        not 0 <= fight.turn_index < len(fight.order)
        or fight.order[fight.turn_index] != fight.current.id
        or fight.current.id in excluded
    ):
        raise ValueError("Inconsistent current native timeline slot")
    projected_turn_index = sum(
        1 for identity in fight.order[: fight.turn_index] if identity not in excluded
    )
    out += struct.pack(">b", projected_turn_index)
    removed = getattr(fight, "native_timeline_removed", None)
    if not isinstance(removed, list) or len(removed) > 127:
        raise ValueError("Missing authoritative native removal statuses")
    removed = [row for row in removed if row["actor_id"] not in excluded]
    if len(removed) > 127:
        raise ValueError("Invalid projected native removal statuses")
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


def recovery_packet(
    fight,
    body,
    *,
    deadline_ms,
    bonus_counts=None,
    excluded_actor_ids=(),
    new_turn=False
):
    if len(body) != 4 or struct.unpack(">i", body)[0] != fight.id:
        raise ValueError("Recovery request belongs to another fight")
    state = timeline(
        fight,
        deadline_ms=deadline_ms,
        bonus_counts=bonus_counts,
        excluded_actor_ids=excluded_actor_ids,
        new_turn=new_turn,
    )
    # fg/fh field envelope: count1,(index0,absolute offset6), data marker0,
    # followed by fcc i16length+SU. cvn carries the complete fg envelope.
    envelope = struct.pack(">BBiBh", 1, 0, 6, 0, len(state)) + state
    if len(envelope) >= 32768:
        raise ValueError("Recovery state exceeds native short length")
    return 12053, struct.pack(">ih", fight.id, len(envelope)) + envelope
