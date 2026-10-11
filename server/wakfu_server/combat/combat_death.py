"""Native cvK12727 death animation from authoritative own fight state."""
import struct


def newly_registered_death_messages(runtime, *, after_sequence):
    """Deliver settled deaths from one private action, once per actor identity."""
    if type(after_sequence) is not int or after_sequence < 0:
        raise ValueError("Actual pre-action death sequence required")
    identities = []
    reported = getattr(runtime, "_reported_deaths", set())
    for event in runtime.fight.events:
        if event["sequence"] <= after_sequence or event.get("kind") != "death":
            continue
        identity = event["actor_id"]
        actor = runtime.fight.actors.get(identity)
        # A reaction may legitimately resurrect the defeated actor before the
        # outer action settles. Do not replay its stale death over the revival.
        if actor is None:
            raise ValueError("Registered death recipient is missing")
        if actor.hp == 0 and identity not in reported and identity not in identities:
            identities.append(identity)
    packets = []
    for identity in identities:
        packets.extend(runtime.prepare_delivery(death_messages(runtime, identity)))
    return packets


def death_messages(runtime, actor_id):
    """NPC state0 removes the timeline member before state2/AnimMort.

    Official dungeon captures send state0 then state2 for each dead NPC.
    aTS.cbj immediately calls D for state0; state2 defers that call until its
    animation callback. Sending only state2 lets the next-turn action overtake
    timeline removal. Player death retains its existing distinct delivery.
    State0 is KO, state1 resurrection, state3 another removal mode. Only
    actual HP-zero actors belonging to this fight can receive a death event.
    Send after the lethal damage action and before normal fight results.
    """
    actor = runtime.fight.actors.get(actor_id)
    if actor is None or actor.hp != 0:
        raise ValueError("Death requires an owned zero-HP fight actor")
    sent = getattr(runtime, "_reported_deaths", set())
    if actor_id in sent:
        raise ValueError("Death was already reported")
    queued = getattr(runtime.fight, "native_finisher_after_death_packets", {})
    if not isinstance(queued, dict):
        raise ValueError("Malformed owned finisher post-death deliveries")
    cleanup = queued.get(str(actor_id), ())
    decoded = []
    for row in cleanup:
        if not isinstance(row, (tuple, list)) or len(row) != 2:
            raise ValueError("Malformed owned finisher cleanup delivery")
        opcode, payload_hex = row
        if opcode not in (12613, 13497, 13560) or not isinstance(payload_hex, str):
            raise ValueError("Unknown owned finisher cleanup delivery")
        payload = bytes.fromhex(payload_hex)
        if (
            len(payload) < 18
            or struct.unpack_from(">i", payload)[0] != runtime.fight.id
        ):
            raise ValueError("Finisher cleanup belongs to another fight")
        decoded.append((opcode, payload))
    from .combat_ordinary_qi_retirement import complete_ordinary_qi_death

    complete_ordinary_qi_death(runtime.fight, actor)
    prefix = runtime._prefix()
    body = prefix + struct.pack(">qB", actor_id, 2)
    from .combat_native_death_status import apply_native_fighter_state_transition

    apply_native_fighter_state_transition(actor, 2)
    runtime._reported_deaths = sent | {actor_id}
    packets = []
    if not actor.controlled:
        packets.append((12727, prefix + struct.pack(">qB", actor_id, 0)))
    packets.extend(((12727, body), runtime._flush()))
    if decoded:
        queued.pop(str(actor_id))
        packets.extend(decoded)
        packets.append(runtime._flush())
    return packets


def despawn_monster(fight, actor_id):
    """ctA12304: remove one owned dead NPC from exploration after12925.

    13082/cwH removes interactive objects; it cannot remove a world NPC.
    """
    actor = fight.actors.get(actor_id)
    if fight.phase != "finished" or actor is None or actor.controlled or actor.hp != 0:
        raise ValueError("Despawn requires a finished own fight and dead NPC")
    return (12304, b"\x00\x00\x01" + struct.pack(">Bq", 1, actor_id))


def dead_world_removals(fight, member_ids):
    """Remove this group's dead exploration actors after native12925 cleanup.

    Validation covers the entire roster before emitting anything. This does
    not finish a registry lease or schedule respawn: those are independent
    authoritative operations, and may already have occurred at victory.
    """
    from .combat_monster_world import remove_message

    identities = tuple(member_ids)
    if not identities or len(set(identities)) != len(identities):
        raise ValueError("Expected a unique owned group roster")
    if fight.phase != "finished":
        raise ValueError("World removal requires a resolved fight")
    dead = []
    for identity in identities:
        actor = fight.actors.get(identity)
        if actor is None or actor.controlled or identity >= 0:
            raise ValueError("Group roster contains a foreign or player actor")
        if actor.hp == 0:
            dead.append(identity)
    return [
        remove_message(dead[offset : offset + 255])
        for offset in range(0, len(dead), 255)
    ]
