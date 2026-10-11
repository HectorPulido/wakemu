"""Native team-private tactical cell reports and eight persistent icon markers.

Installed coNN/coV/coW requests and cuT/cvj replies are the wire authority.
This presentation domain never executes a turn, modifies resources or spells,
releases an ACK barrier, or admits spectators. Callers supply a trusted selected
actor ID; there is no actor/fight identity in the client request body.
"""
import struct
import time

PING = 12543
ADD = 12519
REMOVE = 12597
REQUEST_OPCODES = frozenset((PING, ADD, REMOVE))
PING_COOLDOWN = 5.0  # cKt.reportCell native UI cooldown, milliseconds5000.


def decode(opcode, body):
    if opcode not in REQUEST_OPCODES or not isinstance(body, bytes):
        raise ValueError("Unsupported tactical request")
    expected = 10 if opcode == PING else 11
    if len(body) != expected:
        raise ValueError("Invalid tactical request length")
    position = struct.unpack(">iih", body[:10])
    icon = None if opcode == PING else body[10]
    if icon is not None and icon not in range(8):
        raise ValueError("Unknown native tactical marker icon")
    return position, icon


def _actor(shared, session, actor_id, *, request=True):
    fight = shared.fight
    if fight.phase not in ("placement", "active"):
        raise ValueError("Tactical signaling requires a live fight")
    if (session.map_id, session.instance_id) != (shared.map_id, shared.instance_id):
        raise ValueError("Tactical session is outside this fight location")
    actor = fight.actors.get(actor_id)
    if (
        actor is None
        or not actor.controlled
        or actor.owner_id != session.account_id
        or getattr(actor, "pve_withdrawn", False)
    ):
        raise ValueError("Tactical actor is not owned by this participant")
    # Native UI gates screen picking with biB.a(eHQ.pTu), property72.
    from .combat_ordinary_authority import native_property_catalog

    properties = getattr(actor, "native_fight_properties", None)
    if properties is None:
        properties = native_property_catalog()["player"]["fight_properties"]
    if request and 72 in properties:
        raise ValueError("Native actor property disables tactical cell reports")
    return actor


def _marker_packet(fight_id, position, sender, icon, added):
    return 12226, struct.pack(">iiihqBB", fight_id, *position, sender, icon, added)


def _markers(fight):
    return getattr(fight, "tactical_markers", {})


def handle(registry, session, fight_id, actor_id, opcode, body, *, now=None):
    """Validate and queue one team-only native presentation batch atomically.

    The native client has no request ID. Identical icon mutations are therefore
    idempotent; a stale remove cannot erase a newer location for that icon.
    Pings follow the native five-second UI cooldown per selected actor. Dead
    participants may still signal: native dba has no HP/current-turn gate.
    """
    position, icon = decode(opcode, body)
    observed = time.time() if now is None else now
    shared = registry.lookup(fight_id)
    with shared.lock:
        registry._member(shared, session)
        actor = _actor(shared, session, actor_id)
        fight = shared.fight
        if position not in fight.walkable:
            raise ValueError("Tactical cell is outside authoritative fight terrain")
        markers = _markers(fight)
        team_key = str(actor.team)
        own_markers = markers.get(team_key, {})
        if opcode == PING:
            times = getattr(fight, "tactical_ping_times", {})
            previous = times.get(str(actor.id))
            if previous is not None and observed - previous < PING_COOLDOWN:
                return dict(accepted=False, sequence=shared.sequence, packets=())
            packets = ((13788, struct.pack(">iiihq", fight.id, *position, actor.id)),)
        else:
            previous = own_markers.get(str(icon))
            if (
                opcode == ADD
                and previous is not None
                and tuple(previous["position"]) == position
            ) or (
                opcode == REMOVE
                and (previous is None or tuple(previous["position"]) != position)
            ):
                return dict(accepted=False, sequence=shared.sequence, packets=())
            packets = (
                _marker_packet(fight.id, position, actor.id, icon, opcode == ADD),
            )
        excluded = set(shared.withdrawals)
        for account, participant in shared.participants.items():
            member = fight.actors.get(participant.character_id)
            if member is None or member.team != actor.team:
                excluded.add(account)
        sequence = registry._broadcast(shared, packets, exclude=excluded)
        if opcode == PING:
            times = dict(getattr(fight, "tactical_ping_times", {}))
            times[str(actor.id)] = observed
            fight.tactical_ping_times = times
        else:
            own_markers = dict(own_markers)
            if opcode == ADD:
                own_markers[str(icon)] = dict(position=list(position), sender=actor.id)
            else:
                own_markers.pop(str(icon))
            fight.tactical_markers = dict(markers, **{team_key: own_markers})
        return dict(accepted=True, sequence=sequence, packets=packets)


def snapshots(registry, session, fight_id):
    """Rehydrate the authenticated participant's team icons, never old pings."""
    shared = registry.lookup(fight_id)
    with shared.lock:
        registry._member(shared, session)
        actor = _actor(shared, session, session.character_id, request=False)
        return tuple(
            _marker_packet(
                shared.fight.id, tuple(row["position"]), row["sender"], int(icon), True
            )
            for icon, row in sorted(
                _markers(shared.fight).get(str(actor.team), {}).items()
            )
        )
