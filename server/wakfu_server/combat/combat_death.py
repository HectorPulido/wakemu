"""Native cvK12727 death animation from authoritative own fight state."""
import struct


def death_messages(runtime, actor_id):
    """State2 dispatches aTS.r (death/AnimMort) and B (fight.die).

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
    body = runtime._prefix() + struct.pack(">qB", actor_id, 2)
    runtime._reported_deaths = sent | {actor_id}
    return [(12727, body), runtime._flush()]


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
